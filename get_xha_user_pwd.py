import requests
import json
import random
import subprocess
import syslog

def print(*a, sep=' '): syslog.syslog(sep.join(map(str, a)))

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("-i", "--interface", help="网卡接口名称 interface")
args = parser.parse_args()

def check_connectivity_ping(host, interface):
    command = ['ping', '-I', interface, '-c', '1', host]  # -n 1 on windows, -c 1 on linux
    try:
        result = subprocess.check_call(command, timeout=2)
        return result == 0
    except subprocess.TimeoutExpired:
        print(f"接口 {interface}：Ping to {host} timed out.")
        return False
    except subprocess.CalledProcessError:
        return False
    except Exception as e:
        print(f"接口 {interface}：Error during ping: {e}")
        return False

device = 0
interface = args.interface
if interface is None:
    print("Please specify the interface name using -i or --interface")
    exit()

# 检测网络联通性
if check_connectivity_ping("223.5.5.5", interface):
    exit()

with open("user_pwd.txt", 'r') as f:
    user_pwd = [i.rstrip('\n\r').split() for i in f.readlines()]

user_pwd_error_or_not_unlimit_combo = []
# 检查是否付费
while True:
    # 随机选择，防止前面有密码错误的用户卡死
    user, pwd = random.choice(user_pwd)
    if user in user_pwd_error_or_not_unlimit_combo:
        continue

    url = f'http://192.168.101.201:801/eportal/portal/page/loadUserInfo?callback=dr1004&lang=zh-CN&program_index=ctshNw1713845951&page_index=V5fmKw1713845966&user_account={user}&wlan_user_ip=0.0.0.0&wlan_user_mac=000000000000&jsVersion=4.1&v=599&lang=zh'
    r = requests.get(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36 Edg/105.0.1343.33',
        'Referer': 'http://192.168.101.201/'
    })
    text = r.text.replace('dr1004(', '').replace(')', '').replace(';', '')
    j = json.loads(text)
    if j['user_info']['user_state'] == "正常" and j['user_info']['available_flow'] in ("0MB", "无限制"):
        url = f"http://192.168.101.201:801/eportal/portal/page/loadOnlineRecord?callback=dr1006&lang=zh-CN&program_index=ctshNw1713845951&page_index=V5fmKw1713845966&user_account={user}&wlan_user_ip=10.169.0.241&wlan_user_mac=000000000000&start_time=2010-01-01&end_time=2100-01-01&start_rn=1&end_rn=5&jsVersion=4.1&v=2399&lang=zh"
        # 获取在线设备
        r = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36 Edg/105.0.1343.33',
            'Referer': 'http://192.168.101.201/'
        })
        text = r.text.replace('dr1006(', '').replace(')', '').replace(';', '')
        j1 = json.loads(text)
        if int(j1['count']) == device:
            # 判断密码是否正确
            url = f"https://xha.ouc.edu.cn:802/eportal/portal/login?callback=dr1003&login_method=1&user_account={user}&user_password={pwd}&wlan_user_ip=0.0.0.0&wlan_user_ipv6=&wlan_user_mac=000000000000&wlan_ac_ip=&wlan_ac_name=&jsVersion=4.1&terminal_type=1&lang=zh-cn&v=2425&lang=zh"
            command = ["curl", url, "--interface", interface]
            result = subprocess.run(command, capture_output=True, text=True)
            result = json.loads(result.stdout[7:-2])
            """
            dr1003({"result":0,"msg":"账号不存在","ret_code":1});
            dr1003({"result":0,"msg":"密码错误","ret_code":1});
            dr1003({"result":1,"msg":"Portal协议认证成功！"});
            dr1003({"result":0,"msg":"IP: 10.142.5.160 已经在线！","ret_code":2});
            """
            if '密码错误' in result['msg']:
                print(f"接口 {interface}： {user} {pwd} 密码错误")
                user_pwd_error_or_not_unlimit_combo.append(user)
            elif '已经在线' in result['msg']:
                print(f"接口 {interface}： 正常在线！")
                break
            elif '认证成功' in result['msg']:
                print(f"接口 {interface}：使用账号{user}登录成功!")
                break
    else:
        user_pwd_error_or_not_unlimit_combo.append(user)
# 删除密码错误或不满足要求的用户
if user_pwd_error_or_not_unlimit_combo:
    sed_i_arg = '/^' + '\\|^'.join(user_pwd_error_or_not_unlimit_combo) + '/d'
    cmd = ['sed','-i', sed_i_arg, '/root/user_pwd.txt']
    subprocess.run(cmd)