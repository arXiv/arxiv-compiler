# arxiv/compiler-worker

FROM arxiv/base:latest

# MySQL is needed for the arxiv-auth package.
RUN yum install -y which mysql mysql-devel

# We're doing d-in-d stuff here, so need Docker in the container.
RUN curl https://get.docker.com/ > getdocker.sh
RUN /bin/sh getdocker.sh

WORKDIR /opt/arxiv

# Install Python dependencies with pipenv.
ADD Pipfile /opt/arxiv/
RUN pip install -U pip pipenv uwsgi
RUN pipenv install

ENV PATH "/opt/arxiv:${PATH}"

ENV LC_ALL en_US.utf8
ENV LANG en_US.utf8
ENV LOGLEVEL 40

ENV ARXIV_HOME "https://arxiv.org"

# Add the code in this repo.
ADD compiler /opt/arxiv/compiler/
ADD wsgi.py /opt/arxiv/
ADD bin/start_worker.sh /opt/arxiv/
ADD bin/start_api.sh /opt/arxiv/

EXPOSE 8000

CMD ["/opt/arxiv/start_api.sh", \
     "--http-socket", ":8000", \
     "-M", \
     "-t 3000", \
     "--manage-script-name", \
     "--processes", "8", \
     "--threads", "1", \
     "--async", "100", \
     "--ugreen", \
     "--mount", "/compiler=wsgi.py", \
     "--logformat", "%(addr) %(addr) - %(user_id)|%(session_id) [%(rtime)] [%(uagent)] \"%(method) %(uri) %(proto)\" %(status) %(size) %(micros) %(ttfb)"]
