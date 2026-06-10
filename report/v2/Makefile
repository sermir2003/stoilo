SLIDES = slides.md
THEME = theme.css
OUT = stoilo-slides
MARP = npx @marp-team/marp-cli

.PHONY: pdf pptx html all clean

all: pdf pptx

pdf:
	$(MARP) --allow-local-files --theme $(THEME) $(SLIDES) -o $(OUT).pdf

pptx:
	$(MARP) --allow-local-files --theme $(THEME) $(SLIDES) -o $(OUT).pptx

html:
	$(MARP) --allow-local-files --theme $(THEME) $(SLIDES) -o $(OUT).html

clean:
	rm -f $(OUT).pdf $(OUT).pptx $(OUT).html
