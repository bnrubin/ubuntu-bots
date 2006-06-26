ALL=$(shell find . -name '???*' -maxdepth 1 -type d -printf '%p.tar.gz\n')

default: $(ALL)

%.tar.gz: %
	tar zcf $@ $<

clean:
	rm -f $(ALL)
