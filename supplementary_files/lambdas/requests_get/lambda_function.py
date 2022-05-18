from time import sleep
import json
import requests

def requests_get(url):
    print(f'url:\n{url}')
    r = requests.get(url)
    try:
        assert r.status_code == 200
    except AssertionError:
        return False
    else:
        response_content = json.loads(r.content)
        print(f'response_content:\n{response_content}')
        return response_content

def lambda_handler(event,context):
    
    class StatusCodeNot200Exception(Exception):
        pass
    
    print(f'event:\n{event}\ncontext:\n{context}')
    
    url = event['Url']
    
    response = requests_get(url)
    
    if not response:
        raise StatusCodeNot200Exception
    else:
        return response