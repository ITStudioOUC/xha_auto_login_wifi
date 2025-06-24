
from enum import IntEnum, auto
from urllib import request
import json
import random
import subprocess

def request_get_text(url, headers={}):
    req = request.Request(url, headers=headers)
    with request.urlopen(req) as response:
        return response.read().decode('utf-8')

def check_connectivity(interface):
    interface_def = interface is None
    if not interface_def:
        command = ['ping']
        if not interface_def:
            command += ["-I", interface]
        host = "223.5.5.5"
        command += ['-c', '1', host]  # -n 1 on windows, -c 1 on linux
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
    else:
        try:
            request_get_text("http://connect.rom.miui.com/generate_204")
            return True
        except:
            return False

class LoginStatus(IntEnum):
    unknown = -3
    not_unlimit = -2
    bad_pwd = -1
    succ = auto()
    used_online = auto()

def login(user, pwd, interface, log, device):
    interface_def = interface is None
    url = f'http://192.168.101.201:801/eportal/portal/page/loadUserInfo?callback=dr1004&lang=zh-CN&program_index=ctshNw1713845951&page_index=V5fmKw1713845966&user_account={user}&wlan_user_ip=0.0.0.0&wlan_user_mac=000000000000&jsVersion=4.1&v=599&lang=zh'
    t = request_get_text(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36 Edg/105.0.1343.33',
        'Referer': 'http://192.168.101.201/'
    })
    text = t.replace('dr1004(', '').replace(')', '').replace(';', '')
    j = json.loads(text)
    if j['user_info']['user_state'] == "正常" and j['user_info']['available_flow'] in ("0MB", "无限制"):
        url = f"http://192.168.101.201:801/eportal/portal/page/loadOnlineRecord?callback=dr1006&lang=zh-CN&program_index=ctshNw1713845951&page_index=V5fmKw1713845966&user_account={user}&wlan_user_ip=10.169.0.241&wlan_user_mac=000000000000&start_time=2010-01-01&end_time=2100-01-01&start_rn=1&end_rn=5&jsVersion=4.1&v=2399&lang=zh"
        # 获取在线设备
        t = request_get_text(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36 Edg/105.0.1343.33',
            'Referer': 'http://192.168.101.201/'
        })
        text = t.replace('dr1006(', '').replace(')', '').replace(';', '')
        j1 = json.loads(text)
        if int(j1['count']) == device:
            # 判断密码是否正确
            url = f"https://xha.ouc.edu.cn:802/eportal/portal/login?callback=dr1003&login_method=1&user_account={user}&user_password={pwd}&wlan_user_ip=0.0.0.0&wlan_user_ipv6=&wlan_user_mac=000000000000&wlan_ac_ip=&wlan_ac_name=&jsVersion=4.1&terminal_type=1&lang=zh-cn&v=2425&lang=zh"
            if interface_def:
                res = request_get_text(url)
            else:
                command = ["curl", url, "--interface", interface]
                res = subprocess.check_output(command, text=True)
            result = json.loads(res[7:-2])
            """
            dr1003({"result":0,"msg":"账号不存在","ret_code":1});
            dr1003({"result":0,"msg":"密码错误","ret_code":1});
            dr1003({"result":1,"msg":"Portal协议认证成功！"});
            dr1003({"result":0,"msg":"IP: 10.142.5.160 已经在线！","ret_code":2});
            """
            msg = ""
            if not interface_def:
                log(f"使用接口 {interface} 进行请求")
                msg += f"接口 {interface}： "
            if '密码错误' in result['msg']:
                log(f"{user} {pwd} 密码错误")
                return LoginStatus.bad_pwd
            elif '已经在线' in result['msg']:
                msg += "正常在线！"
                return LoginStatus.used_online
            elif '认证成功' in result['msg']:
                msg += f"使用账号{user}登录成功!"
                return LoginStatus.succ
            log(msg)
        return LoginStatus.unknown
    else:
        return LoginStatus.not_unlimit

def login_till_succ(user_pwd_gen, bad_user_callback=lambda u: None, interface=None, log=print):
    '''
    user_pwd_gen will be called multiply times until login succeeds.
    '''
    device = 0  # Final[int]
    # 检查是否付费
    not_succ = True
    while not_succ:
        (user, pwd) = user_pwd_gen()
        ret = login(user, pwd, interface, log, device)
        not_succ = ret < 0

        if ret in {LoginStatus.bad_pwd, LoginStatus.not_unlimit}:
            bad_user_callback(user)


def main(args, warn, log):
    interface = args.interface
    file = args.file

    interface_def = interface is None
    if interface_def:
        warn("no interface given by -i or --interface, use default route")

    # 检测网络联通性
    if check_connectivity(interface):
        exit()

    with open(file, 'r') as f:
        user_pwd = [i.rstrip('\n\r').split() for i in f.readlines()]

    # login
    user_pwd_error_or_not_unlimit_combo_idx = set()
    cur_lku_user_idx = 0
    def user_pwd_getter():
        # 随机选择，防止前面有密码错误的用户卡死
        user_index = random.randrange(len(user_pwd))
        if user_index in user_pwd_error_or_not_unlimit_combo_idx:
            return user_pwd_getter()
        (user, pwd) = user_pwd[user_index]
        return (user, pwd)

    def bad_user_callback(_):
        user_pwd_error_or_not_unlimit_combo_idx.add(cur_lku_user_idx)

    login_till_succ(user_pwd_getter, bad_user_callback, interface=interface, log=log)


    # 删除密码错误或不满足要求的用户
    with open(file, 'w') as f:
        for i in range(len(user_pwd)):
            if i in user_pwd_error_or_not_unlimit_combo_idx:
                user_pwd_error_or_not_unlimit_combo_idx.remove(i)
            else:
                t = user_pwd[i]
                f.write(t[0])
                f.write(' ')
                f.write(t[1])
                f.write('\n')

if __name__ == "__main__":
    import argparse
    import warnings
    import syslog
    def log(*a, sep=' '): syslog.syslog(sep.join(map(str, a)))
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--interface", help="网卡接口名称 interface")
    parser.add_argument("-f", "--file", help="用户密码文件路径", default="user_pwd.txt")
    args = parser.parse_args()
    main(args, warnings.warn, log)
