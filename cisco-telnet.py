import datetime
import keyring
import mysql.connector
import os
import pymysql
import serial.tools.list_ports
import signal
import subprocess
import sys
import threading
import time

from dhcp_leases import DhcpLeases
from pick import pick
from serial import *
from telnetlib import Telnet
from time import sleep


dhcpstatus = os.system('systemctl status isc-dhcp-server.service >/dev/null 2>&1')
tftpstatus = os.system('systemctl status tftpd-hpa >/dev/null 2>&1')
dbpw = keyring.get_password("172.28.88.47", "simdbuploader")


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def ping_host(host):
    status = subprocess.run(["ping", "-c", "3", host], capture_output=True)
    if status.returncode == 0:
        return True
    else:
        return False


def dbquery(select, from_DB, where, value):
    db = pymysql.connect(host="172.28.88.47",user="simdbuploader",password=dbpw,database="simdb")
    cursor = db.cursor()
    cursor.execute("SELECT {} FROM simdb.{} WHERE {}='{}'".format(select, from_DB, where, value))
    result = cursor.fetchall()
    for row in result:
        result = row[0]
    result = str(result)
    result = result.strip()
    return(result)
    cursor.close()
    db.close()


def simdb_Check(select):
    try:
        db = pymysql.connect(host="172.28.88.47",user="simdbuploader",password=dbpw,database="simdb")
        cursor = db.cursor()
        cursor.execute("SELECT {} FROM simdb.manufacturingorder WHERE moremaining!='0'".format(select))
        vf = cursor.fetchall()
        vf = [i[0] for i in vf]
        return(vf)
        cursor.close()
        db.close()
    except Exception as e:
        print(e)
        return(False)


orders = simdb_Check("monumber")
newlist = []
for i in orders:
    remaining = dbquery("moremaining", "manufacturingorder", "monumber", i)
    test = i+" - "+remaining
    newlist.append(test)
remaining = simdb_Check("moremaining")


title = 'Select MO (Remaining units is listed after each MO): '
options = newlist
mo, index = pick(options, title)
mo = mo.split(" ")[0]


if dhcpstatus == 768:
    print(f"{bcolors.WARNING}DHCP-server is not running. Trying to start{bcolors.ENDC}")
    os.system('sudo systemctl start isc-dhcp-server.service >/dev/null 2>&1')
    time.sleep(5)
    dhcpstatus = os.system('systemctl status isc-dhcp-server.service >/dev/null 2>&1')
    if dhcpstatus == 768:
        print(f"{bcolors.FAIL}Unable to start DHCP-server. Aborting script.{bcolors.ENDC}")
        quit()
    elif dhcpstatus == 0:
        print(f"{bcolors.OKBLUE}DHCP-server is now running. Continuing.{bcolors.ENDC}")


if tftpstatus == 768:
    print(f"{bcolors.WARNING}TFTP-server is not running. Trying to start{bcolors.ENDC}")
    os.system('sudo systemctl start tftpd-hpa >/dev/null 2>&1')
    time.sleep(5)
    tftpstatus = os.system('systemctl status tftpd-hpa >/dev/null 2>&1')
    if tftpstatus == 768:
        print(f"{bcolors.FAIL}Unable to start TFTP-server. Aborting script.{bcolors.ENDC}")
        quit()
    elif tftpstatus == 0:
        print(f"{bcolors.OKBLUE}TFTP-server is now running. Continuing.{bcolors.ENDC}")


sap = dbquery("moarticle", "manufacturingorder", "monumber", mo)
customerid = dbquery("customerid", "articles", "articlenumber", sap)
projectid = dbquery("projectid", "articles", "articlenumber", sap)
dbfirmware = dbquery("impversion", "articles", "articlenumber", sap)
dbconfig = dbquery("config", "articles", "articlenumber", sap)


password = b"Cisco"
if "ICE4" in dbconfig and "1.2" not in dbconfig:
    confpassword = b"a4tg#gj97gm"
    confuser = b"Cisco"
elif "1.2" in dbconfig and "ICE4" in dbconfig:
    confpassword = b"930fqdjkDO"
    confuser = b"admin"
elif "Sauerland" in dbconfig:
    confpassword = b"p1lu77aD!G"
    confuser = b"Cisco"


def main(host,mac,now):
    try:
        start = time.time()
        password = b"Cisco"
        try:
            tn = Telnet(host)
            tn.write(b"en\r\n")
            logincheck = tn.read_until(b"Login invalid", timeout=10)
            if b"Password required, but none set" in logincheck:
                del active_ips[mac]
                sys.exit()
        except Exception:
            del active_ips[mac]
            sys.exit()
        print("Starting new loop for host {}, MAC: {}".format(host, mac))
        tn = Telnet(host)
        tn.write(b"Cisco\r\n")
        tn.write(b"Cisco\r\n")
        #login(host)
        tn.write(b"en\r\n")
        tn.write(b"Cisco\r\n")
        logincheck = tn.read_until(b"Login invalid", timeout=10)
        if b"Login invalid" in logincheck:
            print("Failed to login. Aborting script")
            sys.exit()

        tn.write(b"show version | include Top Assembly Serial Number\r\n")
        serial = tn.read_until(b"FIN\n", timeout=5)
        serial = serial.decode()
        serial = serial.split(":")
        serial = serial[1]
        serial = serial.split("\n")
        serial = serial[0]
        serial = serial.strip()

        tn.write(b"show version | include System image file is\r\n")
        fw = tn.read_until(b"FIN\n", timeout=5)
        fw = fw.decode()
        fw = fw.split('System image file is "flash:/')
        fw = fw[1]
        fw = fw.split('/')
        fw = fw[0]
        fw = fw.replace("mx", "tar")

        dbfirmbyte = dbfirmware.encode()
        firmware_expect = [b"%b" % dbfirmbyte]
        tn.write(b"dir flash:\n")

        dbfirmnotar = dbfirmware[:-4]
        dbfirmnotar = dbfirmnotar.replace("tar", "mx")
        dbfirmnotarbyte = dbfirmnotar.encode()
        dbfirmcheck = tn.read_until(b"%s" % dbfirmnotarbyte, timeout=5)
        if dbfirmnotarbyte not in dbfirmcheck:
            tn.write(b"\r\n")
            tn.write(b"archive download-sw /overwrite tftp://10.101.0.2/%b\r\n" % dbfirmbyte)
            tn.read_until(b"archive download: takes")
            #print(serial+" Firmware flash completed")
            tn.write(b"\r\n")
            sleep(1)
            #print(serial+" Restarting unit after firmware flash")
            sleep(1)
            tn.write(b"\r\n")
            sleep(1)
            tn.write(b"reload\r\n")
            sleep(1)
            tn.write(b"\r\n")
            sleep(1)
            tn.close()
            sleep(1)
            sleep(60)
            timer = 0
            while True:
                if timer >= 30:
                    print(serial+" Host did not respond in the given time. Aborting")
                    sys.exit()
                if ping_host(host):
                    #print(serial+" Host is up")
                    sleep(1)
                    tn.open(host)
                    sleep(1)
                    break
                else:
                    #print(serial+" Waiting for host to reboot")
                    sleep(10)
                timer+=1
            tn.write(b"Cisco\r\n")
            sleep(1)
            tn.write(b"Cisco\r\n")
            #login(host)
            tn.write(b"en\r\n")
            tn.write(b"Cisco\r\n")
            logincheck = tn.read_until(b"Login invalid", timeout=10)
            if b"Login invalid" in logincheck:
                print(serial+" Failed to login. Aborting script")
                sys.exit()
        #else:
            #print(serial+" Firmware already flashed")

        dbconfbyte = dbconfig.encode()
        tn.write(b"copy tftp://10.101.0.2/%b nvram:startup-config\n" % dbconfbyte)
        #print(serial+" Waiting for new config to apply")
        sleep(5)
        tn.write(b"\r\n")
        sleep(30)
        #print(serial+" Restarting unit")
        sleep(1)
        tn.write(b"\r\n")
        sleep(1)
        tn.write(b"reload\r\n")
        sleep(1)
        tn.write(b"\r\n")
        sleep(1)
        tn.close()
        sleep(60)
        timer = 0
        while True:
            if timer >= 30:
                print(serial+" Host did not respond in the given time. Aborting")
                sys.exit()
            if ping_host(host):
                #print(serial+" Host is up")
                break
            else:
                #print(serial+" Waiting for host to reboot")
                sleep(10)
            timer+=1

        try:
            tn = Telnet(host)
            print(serial+" Unit is still accessible through telnet, which it shouldn't be. Config failed")
            sys.exit()
        except Exception:
            #print(serial+" Config successful")
            pass
        # tn.write(b"admin\r\n")
        # tn.write(b"%b\r\n" % confpassword)
        # #login(host)
        # tn.write(b"en\r\n")
        # tn.write(b"%b\r\n" % confpassword)
        # logincheck = tn.read_until(b"Login invalid", timeout=10)
        # if b"Login invalid" in logincheck:
        #     print("Failed to login. Aborting script")
        #     sys.exit()
        # login(host)
        # if tn.expect(promptlist, timeout=.1)[0] == 0:
        #     password = b"Cisco"
        # elif tn.expect(promptlist, timeout=.1)[0] == 1:
        #     password = b"a4tg#gj97gm"
        # elif tn.expect(promptlist, timeout=.1)[0] == 2:
        #     password = b"p1lu77aD!G"
        try:
            dbpw = keyring.get_password("172.28.88.47", "simdbuploader")
            mydb = mysql.connector.connect(
            host="172.28.88.47",
            user="simdbuploader",
            password=dbpw,
            database="simdb"
            )
            mycursor = mydb.cursor()
            sql = "INSERT INTO simdb.cisco (customerid,projectid,sapnumber,serial,firmware,config,mac,manufacturingorder) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            val = (customerid,projectid,sap,serial,dbfirmware,dbconfig,mac,mo)
            mycursor.execute(sql, val)
            mydb.commit()
        except Exception:
            print("Unexpected error during database upload")
            print(Exception)

        try:
            db = pymysql.connect(host="172.28.88.47",user="simdbuploader",password=dbpw,database="simdb")
            cursor = db.cursor()
            cursor.execute("SELECT unitid FROM simdb.cisco WHERE serial='{}'".format(serial))
            unitid = cursor.fetchall()
            for row in unitid:
                unitid = row[0]
            unitid = str(unitid)
            unitid = unitid.strip()
            db.close()
        except Exception:
            print("Unexpected error during unitid fetch")
            print(Exception)
        try:
            if unitid == "None":
                print(f"{bcolors.WARNING}{serial} Unable to verify that the information was uploaded to the database{bcolors.ENDC}")
                print(f"{bcolors.FAIL}{serial} Database upload verification FAIL{bcolors.ENDC}")
            elif unitid != "None":
                db = pymysql.connect(host="172.28.88.47",user="simdbuploader",password=dbpw,database="simdb")
                cursor = db.cursor()
                cursor.execute("SELECT moremaining FROM simdb.manufacturingorder WHERE monumber='%s'" % (mo))
                vf = cursor.fetchall()
                for row in vf:
                    vf = row[0]
                vf = str(vf)
                vf = vf.strip("("")"",""'")
                vf = int(vf)
                vf -= 1
                db.close()
                db = pymysql.connect(host="172.28.88.47",user="simdbuploader",password=dbpw,database="simdb")
                cursor = db.cursor()
                cursor.execute("UPDATE simdb.manufacturingorder SET moremaining ='{}' WHERE monumber ='{}'".format(vf,mo))
                db.commit()
                db.close()
                print(f"{bcolors.OKGREEN}{serial} Database upload verification PASS{bcolors.ENDC}")
                end = time.time()
                endtime = (end - start)
                #print(serial, " ", "Total time: ",endtime)
                myfile = open('{}.txt'.format(now), 'a')
                myfile.write(mac)
                myfile.close()
                print("\a")
        except Exception:
            print(Exception)
            
    except Exception:
        del active_ips[mac]
        sys.exit()


if __name__ == "__main__":
    print("Initial start")
    now = datetime.datetime.now()
    now = "configured_units"+now.strftime("%Y-%m-%d-%H:%M:%S")
    myfile = open('{}.txt'.format(now), 'w')
    myfile.close()
    myfile = open('{}.txt'.format(now), 'r')
    myfile_content=myfile.read()
    myfile.close()
    active_ips = {}
    while True:
        try:
            ports = serial.tools.list_ports.comports()
        except Exception:
            pass
        for p in ports:
            try:
                port = p.device
                if "/dev/ttyUSB" in port:
                    try:
                        console = serial.Serial(
                        port,
                        baudrate=9600,
                        parity=serial.PARITY_NONE,
                        stopbits=STOPBITS_ONE,
                        bytesize=EIGHTBITS,
                        timeout=8
                        )
                        console.write(b"\r\n")
                        sleep(.1)
                        console.write(b"en\r\n")
                        sleep(.1)
                        console.write(b"Cisco\r\n")
                        sleep(.1)
                        console.write(b"capwap ap autonomous\n")
                        sleep(.1)
                        console.write(b"yes\n")
                        sleep(.1)
                        console.write(b"\r\n")
                    except Exception:
                        pass
            except Exception:
                pass
        sleep(90)
        leases = DhcpLeases('/var/lib/dhcp/dhcpd.leases')
        current = leases.get_current()
        for k, v, in current.items():
            mystring = str(v)
            mystring = mystring.split(" ")
            if k in active_ips or k in myfile_content:
                pass
            else:
                for a, b in active_ips.items():
                    if b == mystring[1]:
                        del active_ips[a]
                active_ips[k] = mystring[1]
                host = mystring[1]
                mac = k
                t = threading.Thread(target=main, args=(host, k, now,))
                t.start()
                sleep(1)
