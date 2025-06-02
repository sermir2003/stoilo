FROM ubuntu:24.04

# Install BOINC client
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y boinc-client curl

# Adjust bashrc
COPY bashrc /root/bashrc
RUN cat /root/bashrc >> /root/.bashrc

# Prepare entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
