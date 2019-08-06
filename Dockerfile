# arxiv/compiler

ARG BASE_VERSION=0.16.1

FROM arxiv/base:${BASE_VERSION}

WORKDIR /opt/arxiv/

COPY Pipfile Pipfile.lock /opt/arxiv/
RUN pipenv install && rm -rf ~/.cache/pip

ENV PATH="/opt/arxiv:${PATH}" \
    LOGLEVEL=40 \
    ARXIV_HOME="https://arxiv.org" \
    APPLICATION_ROOT="/"

# Add the code in this repo.
COPY wsgi.py uwsgi.ini app.py /opt/arxiv/
COPY compiler/ /opt/arxiv/compiler/

EXPOSE 8000

ENTRYPOINT ["pipenv", "run"]
CMD ["uwsgi", "--ini", "/opt/arxiv/uwsgi.ini"]
