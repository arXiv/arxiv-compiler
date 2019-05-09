Architecture
============

This section provides a high-level overview of the compilation service,
including its context within the arXiv software system, the primary containers
by which the service is comprised, and the main functional components within
those containers.

Context
-------
The compilation service encapsulates the core TeX compilation functionality
of the arXiv system. This functionality is leveraged in four contexts:

1. Compilation of submission content (TeX, PS) to PDF during the submission
   process so that the submitter can preview their e-print as it will appear
   on arXiv.
#. Providing compiled PDFs during moderation, to facilitate quality assurance
   checks and moderator review.
#. Compilation of PDF, PS, DVI, and other derived formats at announcement time,
   to be included in the canonical record and distributed via the public
   website.
#. Compilation of sources provided by API consumers, e.g. for overlay journals
   or authoring platforms to validate compatibility with arXiv and/or provide
   previews to authors.

The current implementation of the compiler service focuses on the first two
contexts, specifically on PDF outputs.

The third context (announcement) will be supported during later milestones of
the arXiv-NG project.

The fourth context is currently aspirational.

Containers
----------
The compilation service is deployed as three containers:

1. The compiler API, a Flask WSGI application that handles requests for
   compilation, dispatches compilation tasks to the worker, and provides access
   to compiled products and logs.
#. The compiler worker, a Celery application that handles compilation tasks
   by retrieving source content, executing the
   [converter](https://github.com/arXiv/arxiv-converter), and storing the
   resultant products and logs.
#. A Docker-in-Docker (DinD) container, within which the converter image is
   executed. The DinD exposes its API to the compiler worker.

The API and worker containers rely on two infrastructure services:

1. A Redis cluster used as a task queue and result backend, typically shared
   within a deployment namespace.
2. S3 bucket(s) for storing compilation products and logs.


Components
----------
The API and worker containers are composed from the same set of components,
the :py:mod:`compiler` package. This package follows the patterns described
in :std:doc:`arxitecture:crosscutting/services`.

:mod:`compiler.domain` provides the core concepts and data structures for the
compiler service.

:mod:`compiler.factory` provides the :func:`create_app` factory for generating
the compiler API WSGI application.

:mod:`compiler.routes` provides the API blueprint.

API request controllers can be found in :mod:`compiler.controllers`.

Two service integration modules can be found in :mod:`compiler.services`:

1. :mod:`compiler.services.filemanager` provides integration with the
   filemanager service, to retrieve source content for submissions.
2. :mod:`compiler.services.store` provides integration with the S3 buckets
   used to store compilation products and logs.

Dispatching and execution of compilation tasks is implemented in
:mod:`compiler.compiler`.
