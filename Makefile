MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

%.pdf: %.md %.bib
	pandoc -C --csl=$(MAKEFILE_DIR)publishing/ieee.csl --bibliography=$*.bib $< -o $@

