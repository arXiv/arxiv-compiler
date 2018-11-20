import asyncio
from itertools import chain
import json
import logging
import random
import requests

def generate_arxiv_id():
    year = random.randint(9,17)
    month = random.randint(1,12)
    id = random.randint(1,2500)

    return f"{year:02d}{month:02d}.{id:05d}"

def payload(id):
    return {
        "source_id" : id,
        # TODO: Update with actual checksum
        "checksum" : "\"Tue, 02 Feb 2016 01:04:33 GMT\"", 
        "format" : "pdf",
        "force" : True
        }

def check_status(task_url):
    r = requests.get(task_url)
    print(r)
    try:
        data = r.json()
        return data['status']['status']
    except:
        if r.status_code == 404:
            return 'pending'

async def test_compilation(arxiv_id=None):
    """ returns (arxiv_id: str, success: Bool) """
    if arxiv_id is None:
        arxiv_id = generate_arxiv_id()
    data = json.dumps(payload(arxiv_id))
    logging.debug(f"submitting task for {arxiv_id}")
    r = requests.post("http://localhost:8000/", data=data)
    task_url = r.headers['Location']

    status = 'in_progress'
    while status in ['in_progress', 'pending']:
        status = check_status(task_url)
        print(status)
        await asyncio.sleep(10)

    if status == 'failed':
        return (arxiv_id, False)
    elif status == 'completed':
        return (arxiv_id, True)

async def main(N=1):
    arxiv_id, success = await test_compilation('1601.00004')
    print(arxiv_id, success)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(main())
    # asyncio.run(main()) # TODO: Replace above block when upgraded to py37
