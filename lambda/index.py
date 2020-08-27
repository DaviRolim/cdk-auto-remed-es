import json
import urllib3

http = urllib3.PoolManager()

def item_mapper(item):
  new_item = {}
  for key, value in item.items():
    new_item[key] = value.get('S')
  return new_item

        
def handler(event, context):
    print(event)
    records = event['Records'][0]
    item = records['dynamodb']['NewImage']
    response = 'success'
    if item.get('status').get('S') in ['NON_COMPLIANT', 'COMPLIANT']:
        try:
            new_item = item_mapper(item)
            new_item.pop('execution_arn')
            new_item['remediation_status'] = new_item.pop('status')
            print(new_item)
            headers = {'Content-Type': 'application/json'}
            r = http.request('POST',
                            'https://yc2b7l7z0j.execute-api.sa-east-1.amazonaws.com/prod',
                            body=json.dumps(new_item).encode('utf8'),
                            headers=headers)
            print(r.data)
            return r.data
        except Exception as e:
            print(e)
            return "catched error -> " + str(e)
    return response