#!/bin/bash

set -eu  # -e - stop on error, -u - stop on unset variable


echo "[Main] Starting entrypoint for BOINC server container"


DB_TIMEOUT=3
echo "[Connect] Waiting for database at $DB_HOST..."
until mysql --host="$DB_HOST" --user="$DB_USER" --password="$DB_PASSWORD" --execute="SELECT 1;" >/dev/null 2>&1; do
  echo "[Connect] Database is not available yet, retrying in $DB_TIMEOUT seconds..."
  sleep "$DB_TIMEOUT"
done
echo "[Connect] Database is available!"


if [ ! -d "$PROJECT_DIR" ]; then

  echo "[Project] Creating project $PROJECT_NAME..."
  cd "$BOINC_SRC_DIR"/tools
  ./make_project \
    --url_base "$URL_BASE" \
    --db_host "$DB_HOST" \
    --db_name "$DB_NAME" \
    --db_user "$DB_USER" \
    --db_pass "$DB_PASSWORD" \
    --drop_db_first \
    --project_root "$PROJECT_DIR" \
    --no_query \
    "$PROJECT_NAME"
  
  cp "$PROJECT_DIR"/bin/script_validator "$PROJECT_DIR"/bin/script_validator_2
  cp "$PROJECT_DIR"/bin/script_assimilator "$PROJECT_DIR"/bin/script_assimilator_2

  echo "[Project] Project created!"


  echo "[Database] Initializing database after project creation..."
  for file in "$DEPLOY_DIR"/db/*.sql; do
    echo "[Database] Executing $file..."
    mysql --host="$DB_HOST" --user="$DB_USER" --password="$DB_PASSWORD" --database="$DB_NAME" < "$file"
  done
  echo "[Database] Database initialized!"


  echo "[Apache] Configuring Apache for boinc..."
  chown -R www-data:www-data "$PROJECTS_DIR"
  # www-data needs to have write permissions for some files in the project directory. However, the line above
  # 1. too rude, as it gives www-data permissions to more files than apache2 needs;
  # 2. does not grant such permissions to files that will be created later (as in this entrypoint.sh, and by BOINC daemons).
  # So I am not sure that we won't encounter apache2 permissions errors in the future.
  cat >> "$PROJECT_DIR"/"$PROJECT_NAME".httpd.conf <<EOF
    LimitXMLRequestBody 1073741824
    LimitRequestBody 1073741824
EOF
  ln -s "$PROJECT_DIR"/"$PROJECT_NAME".httpd.conf /etc/apache2/sites-available/"$PROJECT_NAME".conf
  a2dissite 000-default
  a2ensite "$PROJECT_NAME".conf
  a2enmod cgi
  echo "[Apache] Apache configured!"


  echo "[Apps] Moving apps, templates and project.xml..."
  mv "$WORKERS_DIR"/apps -T "$PROJECT_DIR"/apps
  mv "$WORKERS_DIR"/templates -T "$PROJECT_DIR"/templates
  mv "$WORKERS_DIR"/project.xml -t "$PROJECT_DIR"
  echo "[Apps] Applying bin/xadd"
  cd "$PROJECT_DIR"
  bin/xadd
  echo "[Apps] Applying bin/update_versions"
  cd "$PROJECT_DIR"
  yes | bin/update_versions
  echo "[Apps] Applications deployed!"


  echo "[Daemons] Deploying daemons..."

  echo "[Daemons] Create links to daemons..."
  LINKS=(
    raboshka_work_generator
    raboshka_assimilator
    raboshka_validator_init
    raboshka_validator_compare
  )
  for name in "${LINKS[@]}"; do
    if [[ $name == raboshka_validator_* ]]; then
      module="raboshka_validator"
      # extract “init” or “compare” from the link name
      args="--${name#raboshka_validator_}"
    else
      module="$name"
      args=""
    fi
    link_file="$PROJECT_DIR/bin/$name"
    cat > "$link_file" <<EOF
#!/usr/bin/env bash
cd "$DAEMONS_DIR"
exec python3 -m $module ${args:+$args} "\$@"
EOF
    # ${args:+$args} expands to `[--init/--compare] "$@"`, "$@" is for passing command line arguments to the daemon
    chmod +x "$link_file"
    echo "[Daemon] Created link $link_file -> $DAEMONS_DIR/$module ${args:+$args}"
  done

  echo "[Daemons] Adding daemons to config.xml..."
  chmod +x "$DEPLOY_DIR"/add_daemons.py
  "$DEPLOY_DIR"/add_daemons.py "$PROJECT_DIR"/config.xml "$DAEMONS_DIR"/add_demons.xml

  echo "[Daemons] Daemons deployed!"


  echo "[Cron] Configuring cron..."
  # WARNING: this overwrites the cronjob, it is assumed that no one else uses them.
  crontab "$PROJECT_DIR"/"$PROJECT_NAME".cronjob
  echo "[Cron] Cron configured!"

  echo "[Ops] Setting ${PROJECT_NAME}_ops password..."
  cd "$PROJECT_DIR"/html/ops
  htpasswd -b -c .htpasswd "$OPS_LOGIN" "$OPS_PASSWORD"
  echo "[Ops] Ops ${PROJECT_NAME}_ops set!"

  echo "[Web] Setting project name and copyright..."
  find "$PROJECT_DIR/html" -type f -exec sed -i 's/REPLACE WITH PROJECT NAME/STOILO/g' {} +
  find "$PROJECT_DIR/html" -type f -exec sed -i 's/REPLACE WITH COPYRIGHT HOLDER/Sergei Mironov/' {} +
  echo "[Web] Project name and copyright set!"

else
  echo "[Main] Directory $PROJECT_NAME already exists, project configuration skipped"
fi


echo "[Main] Starting all daemons..."
cd "$PROJECT_DIR"
bin/start
echo "[Main] All daemons started!"


echo "[Main] Launching supervisord..."
mkdir -p "$PROJECT_DIR"/svc_logs/  # directory for supervisor logs
exec /usr/bin/supervisord -c ${DEPLOY_DIR}/supervisord.conf
