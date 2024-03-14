import hmac
import hashlib
from urllib.parse import urlparse, parse_qs
import datetime
import urllib.request
import urllib.parse
import requests
import json

# Use your AppSecret as the secret key and hmac-sha256 hashing algorithm to calculate the signature.
# request: https://{host}/api/orders?limit=20&timestamp=1623812664&app_key=12345&access_token=88888888
# 1.Extract all query param EXCEPT ' sign ', ' access_token ', reorder the params based on alphabetical order.
# 2.Concat all the param in the format of {key}{value}
# 3.Append the request path to the beginning
# 4.Wrap string generated in step 3 with app_secret.
# 5.Initiate the algorithm based on app_secret and produce the digest.
# 6.Encode the digest byte stream in hexadecimal.
# 7.Use sha256 to generate sign with salt(secret).
# 8.Timestamp valid within 5 minutes.

def get_timestamp():
    current_datetime = datetime.datetime.now()
    return int(current_datetime.timestamp())

def cal_sign(request_url, app_secret, body=None):
    parsed_url = urlparse(request_url)
    queries = parse_qs(parsed_url.query)
    keys = [k for k in queries if k not in ("sign", "access_token")]
    keys.sort()
    input_str = ""
    for key in keys:
        input_str += key + queries[key][0]
    input_str = parsed_url.path + input_str
    if body:
        if isinstance(body, dict):
            body = json.dumps(body)
        input_str += body
    input_str = app_secret + input_str + app_secret
    return generate_sha256(input_str, app_secret)

def generate_sha256(input_str, app_secret):
    h = hmac.new(app_secret.encode(), input_str.encode(), hashlib.sha256)
    return h.hexdigest()

def get_cipher_shop_key(app_key, app_secret, token, base_url):
        url = f"{base_url}/authorization/202309/shops"
        headers = {
            "Content-Type": "application/json",
            "x-tts-access-token": f"{token}",
        }
        params = {
            "app_key": app_key,
            "timestamp": get_timestamp(),
            "version": "202309",
        }
        params_signed = urllib.parse.urlencode(params)
        url_signed = f"{url}?{params_signed}"
        
        params['sign'] = cal_sign(url_signed, app_secret)
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            return None

def get_active_shops(app_key, app_secret, token, base_url):
    url = f"{base_url}/seller/202309/shops"  
    headers = {
            "Content-Type": "application/json",
            "x-tts-access-token": f"{token}",
        }
    params = {
            "app_key": app_key,
            "timestamp": get_timestamp(),
            "version": "202309",
        }
    params_signed = urllib.parse.urlencode(params)
    url_signed = f"{url}?{params_signed}"   
    params['sign'] = cal_sign(url_signed, app_secret)
    response = requests.get(url, headers=headers, params=params, timeout=30)
    if response.status_code == 200:
        return response.json().get('data', []).get('shops', [])
    else:
        return None
    

    
    