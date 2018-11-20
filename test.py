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
        await asyncio.sleep(10)
        status = check_status(task_url)
        print(arxiv_id, status)

    if status == 'failed':
        return (arxiv_id, False)
    elif status == 'completed':
        return (arxiv_id, True)

def main(N=1, ids=[]):
    futures = []
    if ids:
        for id in ids:
            futures.append(asyncio.ensure_future(test_compilation(id)))
    else:
        for i in range(N):
            futures.append(asyncio.ensure_future(test_compilation()))

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(asyncio.wait(futures))
    for future in futures:
        arxiv_id, success = future.result()
        print(arxiv_id, success)

if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-N', type=int, default=5)
    group.add_argument('--ids', nargs="+")
    args = parser.parse_args()
    
    main(N=args.N, ids=args.ids)
