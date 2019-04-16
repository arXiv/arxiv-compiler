# arxiv/compiler-worker

FROM arxiv/base:latest

# MySQL is needed for the arxiv-auth package.
RUN yum install -y which mysql mysql-devel && yum -y clean all

# We're doing d-in-d stuff here, so need Docker in the container.
RUN curl https://get.docker.com/ > getdocker.sh
RUN /bin/sh getdocker.sh

WORKDIR /opt/arxiv

# Install Python dependencies with pipenv.
RUN pip install -U pip pipenv uwsgi
ADD Pipfile /opt/arxiv/
RUN pipenv install

ENV PATH "/opt/arxiv:${PATH}"

ENV LOGLEVEL 40

ENV ARXIV_HOME "https://arxiv.org"

# Add the code in this repo.
ADD compiler /opt/arxiv/compiler/
ADD wsgi.py /opt/arxiv/
ADD uwsgi.ini /opt/arxiv/
ADD bootstrap.py /opt/arxiv/
ADD app.py /opt/arxiv/
ADD bin/start_worker.sh /opt/arxiv/
ADD bin/start_api.sh /opt/arxiv/

EXPOSE 8000

ENTRYPOINT ["pipenv", "run"]
CMD ["uwsgi", "--ini", "/opt/arxiv/uwsgi.ini"]
