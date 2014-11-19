From ubuntu:14.04

# Make sure that we download packages from the local network cache
RUN echo 'Acquire::http::Proxy "http://aptcache.f2l.info:3142";' > /etc/apt/apt.conf.d/proxy 

# Refresh the package list to appy the proxy and universe 
RUN apt-get  update

ENV PIP_INDEX_URL http://pypi.f2l.info/root/dev
# Install ruby to let us run puppet
RUN apt-get install -y python python-dev python-pip 
RUN pip install -U pip setuptools
RUN pip install -U flake8 tox

ADD . /src

CMD cd /src && /src/ci
