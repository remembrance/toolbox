ARG ALPINE_VERSION=3.17
FROM alpine:$ALPINE_VERSION

RUN adduser -D unprivileged

ENV PYTHONPATH=/usr/local/lib/python

# base packages
RUN apk -U add \
  gcc \
  musl-dev \
  python3-dev \
  libgit2-dev \
  py3-pip \
  \
  bash \
  ca-certificates \
  bind-tools \
  mariadb-client \
  libgit2 \
  python3 \
  coreutils \
  nmap \
  tcpdump \
  ngrep \
  mtr \
  vim \
  openssh \
  \
  && \
  \
  pip install \
  boto3 \
  pygit2==1.11.1 \
  PyGithub \
  dnspython \
  kubernetes \
  \
  && \
  \
  apk del \
  gcc \
  musl-dev \
  python3-dev \
  libgit2-dev

USER unprivileged

COPY manifest /
