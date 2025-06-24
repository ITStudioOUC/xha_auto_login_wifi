
from sys import maxsize
from enum import IntEnum, auto
from urllib.error import URLError
from urllib import request
from errno import ENETUNREACH
import json
import random
import subprocess

def request_get_text(url, headers={}):
    req = request.Request(url, headers=headers)
    with request.urlopen(req) as response:
        return response.read().decode("utf-8")

class LoginStatus(IntEnum):
    unknown = -maxsize-1
    no_wifi = -3
    not_unlimit = -2
    bad_pwd = -1
    succ = auto()
    used_online = auto()

class Loginer:
    def __init__(self,
        interface = None,
        device = 0,
        log = print,
    ):
        self.interface = interface
        self.device_str = str(device)
        self.log = log
        self.interface_def = interface is None
    def check_connectivity(self):
        interface = self.interface
        if not self.interface_def:
            command = ["ping", "-I", interface]
            host = "223.5.5.5"
            command += ["-c", "1", host]  # -n 1 on windows, -c 1 on linux
            try:
                result = subprocess.check_call(command, timeout=2)
                return result == 0
            except subprocess.TimeoutExpired:
                self.log(f"接口 {interface}：Ping to {host} timed out.")
                return False
            except subprocess.CalledProcessError:
                return False
            except Exception as e:
                self.log(f"接口 {interface}：Error during ping: {e}")
                return False
        else:
            try:
                request_get_text("http://connect.rom.miui.com/generate_204")
                return True
            except:
                return False
    referrer = "http://192.168.101.201/"
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36 Edg/105.0.1343.33",
        "Referer": referrer
    }

    @staticmethod
    def url(last, dr, v):
        return "/eportal/portal/page/" + last + "?callback=dr" + dr + "&v=" + v + \
            "&lang=zh-CN&program_index=ctshNw1713845951&page_index=V5fmKw1713845966&wlan_user_ip=0.0.0.0&wlan_user_mac=000000000000&jsVersion=4.1"

    ip0 = "&wlan_user_ip=0.0.0.0"
    urlloadUserInfo = referrer + url("loadUserInfo", "1004", "599") + ip0
    urlloadOnlineRecord = referrer + url("loadOnlineRecord", "1006", "2399") + "&wlan_user_ip=10.169.0.241&start_time=2010-01-01&end_time=2100-01-01&start_rn=1&end_rn=5"
    urllogin = referrer + url("loadOnlineRecord", "1006", "2399") + ip0 + "&login_method=1&wlan_user_ipv6=&wlan_user_mac=000000000000&wlan_ac_ip=&wlan_ac_name=&terminal_type=1"

    @staticmethod
    def json_from_drnnnn(t):
        "drNNNN(`result`); <- e.g. t.replace('dr1006(', '').replace(')', '').replace(';', '')"
        return json.loads(t[7:-2])
    def login(self, user, pwd):
        interface = self.interface
        interface_def = self.interface_def
        u = "&user_account=" + user

        url = self.urlloadUserInfo + u
        try:
            t = request_get_text(url, headers=self.header)
        except URLError as e:
            if e.reason.errno == ENETUNREACH:
                return LoginStatus.no_wifi
            raise

        j = self.json_from_drnnnn(t)
        # 检查是否付费
        if j["user_info"]["user_state"] == "正常" and j["user_info"]["available_flow"] in ("0MB", "无限制"):
            url = self.urlloadOnlineRecord + u
            # 获取在线设备
            t = request_get_text(url, headers=self.header)
            j1 = self.json_from_drnnnn(t)
            result = LoginStatus.unknown
            if j1['count'] == self.device_str:
                # 判断密码是否正确
                url = self.urllogin + u + "&user_password=" + pwd
                if interface_def:
                    res = request_get_text(url)
                else:
                    command = ["curl", url, "--interface", interface]
                    res = subprocess.check_output(command, text=True)
                j_res = self.json_from_drnnnn(res)
                """
                dr1003({"result":0,"msg":"账号不存在","ret_code":1});
                dr1003({"result":0,"msg":"密码错误","ret_code":1});
                dr1003({"result":1,"msg":"Portal协议认证成功！"});
                dr1003({"result":0,"msg":"IP: 10.142.5.160 已经在线！","ret_code":2});
                """
                msg = ""
                if not interface_def:
                    self.log(f"使用接口 {interface} 进行请求")
                    msg += f"接口 {interface}： "

                j_msg = j_res["msg"]
                if "密码错误" in j_msg:
                    msg += f"{user} {pwd} 密码错误"
                    result = LoginStatus.bad_pwd
                elif "已经在线" in j_msg:
                    msg += "正常在线！"
                    result = LoginStatus.used_online
                elif "认证成功" in j_msg:
                    msg += f"使用账号{user}登录成功!"
                    result = LoginStatus.succ
                self.log(msg)
            return result
        else:
            return LoginStatus.not_unlimit

    def login_till_succ(self, user_pwd_gen, bad_user_callback=lambda u: None):
        """
        user_pwd_gen will be called multiply times until login succeeds.
        """
        not_succ = True
        while not_succ:
            (user, pwd) = user_pwd_gen()
            ret = self.login(user, pwd)
            if ret == LoginStatus.no_wifi:
                raise RuntimeError("not connect to wifi yet")
            not_succ = ret < 0

            if ret in {LoginStatus.bad_pwd, LoginStatus.not_unlimit}:
                bad_user_callback(user)


    def main(self, file, warn, sep=' '):
        interface_def = self.interface_def
        if interface_def:
            warn("no interface given by -i or --interface, use default route")

        # 检测网络联通性
        if self.check_connectivity():
            return

        with open(file, 'r') as f:
            user_pwd = [i.rstrip("\r\n").split(sep) for i in f.readlines()]

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

        self.login_till_succ(user_pwd_getter, bad_user_callback)

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
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-i", "--interface", help="网卡接口名称. If not given, use default route", default=None)
    parser.add_argument("-f", "--file", help="用户密码文件路径, one record each line", default="user_pwd.txt")
    parser.add_argument("-S", "--no-syslog", action="store_true", help="use print over syslog for log")
    parser.add_argument("-s", "--sep", help="separator used in file between user and password", default=' ')
    args = parser.parse_args()

    log = lambda *a: print(*a)
    if args.no_syslog:
        log = lambda *a: syslog.syslog(' '.join(map(str, a)))
    Loginer(args.interface, log=log).main(args.file, warnings.warn, sep=args.sep)
