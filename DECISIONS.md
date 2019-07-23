# Decision log

## 2019-07-23: Don't store task state in S3

In previous versions, both the compilation product (e.g. PDF) and information
about the state of the compilation task were stored in S3. The main driver for
this was to avoid introducing a new state store (e.g. a database) just to store
a little bit of metadata about a compilation task.

As reported by e.g. https://github.com/arXiv/arxiv-submission-ui/issues/123
we ran into some performance issues, and some lost state. Specifically, the
state of the compilation process was not always successfully stored in S3,
leading to an unacceptable split-brain situation. The fix for this seemed to be
to consult the task backend (Redis) for the "real" state of the compilation
task.... which begs the question of why we would store compilation status
metadata anywhere else in the first place.

A simpler approach (that still avoids a database) is to rely entirely on the
task/result backend (Redis) for the state of the compilation process. By
setting [``result_extended =
True``](http://docs.celeryproject.org/en/latest/userguide/configuration.html#result-extended)
and handling failures gracefully, we can ensure that the original parameters
for the compilation (e.g. owner) can always be successfully obtained.

Incidentally, this also speeds up read-only requests for compilation status
by something like 10x.