# arxiv/compiler-worker

FROM arxiv/base:0.15.6

# MySQL is needed for the arxiv-auth package.
RUN yum install -y which mysql mysql-devel && yum -y clean all

WORKDIR /opt/arxiv

ENV PIP_CACHE_DIR /dev/null

# Install Python dependencies with pipenv.
RUN pip install -U pip pipenv uwsgi
ADD Pipfile /opt/arxiv/
RUN pipenv install

ENV PATH "/opt/arxiv:${PATH}"

ENV LOGLEVEL 40

ENV ARXIV_HOME "https://arxiv.org"

# Add the code in this repo.
ADD compiler /opt/arxiv/compiler/
ADD wsgi.py uwsgi.ini app.py bin/start_worker.sh /opt/arxiv/

EXPOSE 8000

ENTRYPOINT ["pipenv", "run"]
CMD ["uwsgi", "--ini", "/opt/arxiv/uwsgi.ini"]
