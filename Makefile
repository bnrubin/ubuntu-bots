ALL=$(shell find . -name '???*' -type d -printf '%p.tar.gz\n')

default: $(ALL)

%.tar.gz: %
	tar zcf $@ $<

clean:
	rm -f $(ALL)
