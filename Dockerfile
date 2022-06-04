FROM debian:unstable AS builder
ARG py=python3

RUN apt update && apt install -y $py wget python3-distutils $py-venv
RUN wget https://bootstrap.pypa.io/get-pip.py
RUN $py get-pip.py

ADD . /build
WORKDIR /build

#RUN $py -m ensurepip
RUN $py -m pip install setuptools

RUN apt install -y gcc make rustc cargo libffi-dev $py-dev

RUN $py -m venv /venv
ENV PATH=/venv/bin:$PATH
RUN python setup.py install


FROM debian:unstable AS runner
LABEL org.opencontainers.image.source https://github.com/satcom886/router_prometheus
ARG py=python3
ENV py=$py

RUN mkdir /config

RUN apt update && apt install -y curl $py $py-venv
#RUN ln -s /pypy/bin/pypy3 /usr/bin/

COPY --from=builder /venv /venv
ENV PATH=/venv/bin:$PATH
#RUN $py -m ensurepip && $py -m pip install --upgrade pip  && $py -m pip install /dist/* && $py -m pip uninstall -y pip && rm -r /dist

# The port instide the container must remain set to 8080 in order for this healthcheck to work
HEALTHCHECK --interval=60s --timeout=5s CMD curl -f http://localhost:8080/ || exit 1
CMD ["python", "-u", "-m", "router_prometheus"]
