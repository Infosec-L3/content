import requests
import json
import yaml

SERVER = demisto.params()['url'][:-1] if demisto.params()['url'].endswith('/') else demisto.params()['url']
TOKEN = demisto.params().get('token')
USE_SSL = not demisto.params().get('insecure', False)
ALERT_URL = SERVER + '/cas/api/v1/alerts/'
ACTIVITY_URL = SERVER + '/api/v1/activities/'
USER_SEARCH = '/cas/api/v1/autocomplete/entities/?search='
HEADERS = {'Authorization': 'Token ' + TOKEN, 'Content-type': 'application/json'}

if not demisto.params()['proxy']:
    del os.environ['HTTP_PROXY']
    del os.environ['HTTPS_PROXY']
    del os.environ['http_proxy']
    del os.environ['https_proxy']

def http_request(url, data, initial):
    if initial is True:
        request = requests.get(url=url, headers=HEADERS)
    else:
        request = requests.post(url=url, headers=HEADERS, json=data, verify=USE_SSL)
    try:
        # Use yaml library to reformat unicode
        output = yaml.load(json.dumps(request.json()))
    except:
        sys.exit('The API response is incorrectly encoded.')
    return output

def mcas_list_alerts():
    limit = demisto.args()['limit']
    severity_raw = demisto.args()['severity']
    if severity_raw == 'Low':
        severity = '0'
    elif severity_raw == 'Medium':
        severity = '1'
    elif severity_raw == 'High':
        severity = '2'
    else:
        severity = '2,1,0'
    data = '{"skip":0,"limit":' + limit + ',"filters":{"resolutionStatus":{"eq":[0]},"severity":{"eq":[' + severity + ']}},"sortField":"date","sortDirection":"desc","performAsyncTotal":true}'
    response = http_request(ALERT_URL, data, False)

    # Obtain json index length
    x = (len(response['data']))
    results = []
    for i in range(0, x):
        ip = 'unknown'
        user = 'unknown'
        email = 'unknown'
        label = 'unknown'
        country = 'unknown'
        policyType = 'unknown'
        policyName = 'unknown'
        url = response['data'][i]['URL']
        root_id = response['data'][i]['_id']
        context_id = response['data'][i]['contextId']
        description_raw = response['data'][i]['description']
        description = description_raw.replace('<p>'," ").replace('</p>'," ").replace('<br>'," ")
        title = response['data'][i]['title']
        timestamp = response['data'][i]['timestamp']
        entities = response['data'][i]['entities']

        # Determine length of entity results in response
        y = (len(entities))

        # iterate through every entity result
        for k in range(0, y):
            if 'em' in entities[k]:
                email = entities[k]['em']
                user = entities[k]['label']
            if 'type' in entities[k]:
                if entities[k]['type'] == 'user':
                    email = entities[k]['label']
                if entities[k]['type'] == 'account':
                    user = entities[k]['label']
                if entities[k]['type'] == 'ip':
                    ip = entities[k]['label']
                if entities[k]['type'] == 'country':
                    country = entities[k]['label']
                if entities[k]['type'] == 'policyRule':
                    policyType = entities[k]['policyType']
                    policyName = entities[k]['label']
        results.append({'ID': root_id, 'title': title, 'description': description, 'policyName': policyName,
        'policyType': policyType, 'timestamp': timestamp, 'user': user, 'email': email, 'ip': ip, 'country': country})
    entry = {'Type' : entryTypes['note'],
                  'Contents' :results,
                  'ContentsFormat' : formats['json'],
                  'HumanReadable': tableToMarkdown('MCAS Alerts', results),
                  'ReadableContentsFormat' : formats['markdown'],
                  'EntryContext' :{'mcas_alert': results}
                 }
    return entry

def mcas_lookup():
    res=True
    user = 'unknown'
    user_id = 'unknown'
    upn_id = 'unknown'
    mcas_ip = demisto.args()['ip']
    url = ACTIVITY_URL
    data = '{"skip":0,"limit":200,"filters":{"ip.address":{"eq":["' + mcas_ip + '"]}},"sortField":"date","sortDirection":"desc","performAsyncTotal":true}'
    response = http_request(ACTIVITY_URL, data, False)

    # Obtain json index length
    x = (len(response['data'])) - 1
    results = []
    # Loop through all data fields based on json index length
    for i in range(0, x):
        # Check for raw data field
        rawDataJson_exist = response['data'][i].get('rawDataJson', 'no_data')
        if rawDataJson_exist != 'no_data':
            userid_exist = response['data'][i]['rawDataJson'].get('UserId', 'no_data')
            Upn_exist = response['data'][i]['rawDataJson'].get('Upn', 'no_data')
            # Check for User_Id field (alerts)
            if userid_exist != 'no_data':
                user_id = (response['data'][i]['rawDataJson']['UserId'])
                results.append({'IP': mcas_ip, 'user_id': user_id})
            if Upn_exist != 'no_data':
                user_id = (response['data'][i]['rawDataJson']['Upn'])
                results.append({'IP': mcas_ip, 'user_id': user_id})

    # Print message if no records found
    if user == 'unknown' and user_id == 'unknown' and upn_id == 'unknown':
        return 'No records found.'
    else:
        # Print csv output of records; export results to context
        entry = {'Type' : entryTypes['note'],
                  'Contents' :results,
                  'ContentsFormat' : formats['json'],
                  'HumanReadable': tableToMarkdown('MCAS list', results),
                  'ReadableContentsFormat' : formats['markdown'],
                  'EntryContext' :{'mcas_ip': results}
                 }
        return entry

def mcas_username():
    res=True
    description = 'unknown'
    mcas_username = demisto.args()['username']
    initial_request = SERVER + USER_SEARCH + mcas_username
    initial_response = http_request(initial_request, description, True)
    uid = (initial_response['records'][0]['id'])
    saas = (initial_response['records'][0]['saas'])
    data = '{"skip":0,"limit":20,"filters":{"resolutionStatus":{"eq":[0]},"entity.entity":{"eq":[{"id":"' + uid + '","saas":' + str(saas) + ',"inst":0}]}},"sortField":"date","sortDirection":"desc","performAsyncTotal":true}'
    response = http_request(ALERT_URL, data, False)

    # Obtain json index length
    x = (len(response['data'])) - 1
    results = []
    if x == 0:
        description_exist = response['data'][0].get('description', 'no_data')
        if description_exist != 'no_data':
            description_raw = (response['data'][0]['description'])
            description = description_raw.replace('<p>',' ').replace('</p>',' ').replace('<br>',' ')
            results.append({'Username': mcas_username, 'description': description})
    else:
        # Loop through all data fields based on json index length
        for i in range(0, x):
            # Check for raw data field
            description_exist = response['data'][i].get('description', 'no_data')
            if description_exist != 'no_data':
                description_raw = (response['data'][i]['description'])
                description = description_raw.replace('<p>',' ').replace('</p>',' ').replace('<br>',' ')
                results.append({'Username': mcas_username, 'description': description})

    # Print message if no records found
    if description == 'unknown':
        return 'No records found.'
    else:
        # Export results to context
        entry = {'Type' : entryTypes['note'],
                  'Contents' :results,
                  'ContentsFormat' : formats['json'],
                  'HumanReadable': tableToMarkdown('MCAS list', results),
                  'ReadableContentsFormat' : formats['markdown'],
                  'EntryContext' :{'mcas_username': results}
                 }
        return entry
try:
    # The command demisto.command() holds the command sent from the user.
    if demisto.command() == 'test-module':
        test = str(requests.get(url=ALERT_URL, headers=HEADERS))
        if test == '<Response [200]>':
            demisto.results('ok')
        else:
            return_error('HTTP Error: ' + str(test))
    elif demisto.command() == 'mcas-list-alerts':
        demisto.results(mcas_list_alerts())
    elif demisto.command() == 'mcas-lookup-ip':
        demisto.results(mcas_lookup())
    elif demisto.command() == 'mcas-lookup-user':
        demisto.results(mcas_username())
except Exception as e:
    return_error('Error has occurred in the MCAS Integration: {error}\n {message}'.format(error=type(e),
                                                                                            message=e.message))