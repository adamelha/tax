import json
import os

f = os.path.join(os.path.dirname(os.path.realpath(__file__)),'config.json')
with open(f, encoding='utf-8') as json_data:
    user_data_dict = json.load(json_data)
    print(user_data_dict)

user_data = {k: user_data_dict[k]['value'] for k in user_data_dict.keys() }
user_data['name'] = user_data['first-name'] + ' ' + user_data['last-name']