SRCs := $(wildcard *.ipynb)
PDFs := $(SRCs:ipynb=pdf)

.PHONY: all

pdf: $(PDFs)

$(PDFs): %.pdf: %.ipynb
	jupyter nbconvert --to pdf $<

build: pdf tgz

tgz: pdf
	cd ..; tar czf ciac.tgz ciac

rebuild: clean build

all: build

clean:
	@rm -rf $(PDFs)