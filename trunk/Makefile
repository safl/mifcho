VER = 0.1

build:
	python setup.py sdist

install:
	cd dist && tar xf *.tar.gz && cd mifcho-$(VER) && python setup.py install

clean:
	rm MANIFEST
	rm -r dist/mifcho-$(VER)
	m dist/mifcho-$(VER).tar.gz
