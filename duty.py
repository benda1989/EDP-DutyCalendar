import os
import json
import socket
import time
import requests
import websocket
import sxtwl
from datetime import datetime
from calendar import Calendar
from PIL import Image, ImageFont, ImageDraw

FONT = "Font01.ttc"  # '/System/Library/Fonts/PingFang.ttc'
WIDTH = 400
HEIGHT = 300
CROW = 5
CCOL = 7
DOWN = int(HEIGHT/(CROW+2))
RIGHT = int(WIDTH/CCOL)
TOPNUM = ["日", "一", "二", "三", "四", "五", "六"]
jqmc = ["冬至", "小寒", "大寒", "立春", "雨水", "惊蛰", "春分", "清明", "谷雨", "立夏", "小满",
        "芒种", "夏至", "小暑", "大暑", "立秋", "处暑", "白露", "秋分", "寒露", "霜降", "立冬", "小雪", "大雪"]
yuefen = ["", "正月", "二月", "三月", "四月", "五月",
          "六月", "七月", "八月", "九月", "十月", "十一月", "十二月"]
nlrq = ["", "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十", "十一", "十二", "十三", "十四",
        "十五", "十六", "十七", "十八", "十九", "二十", "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十"]


BMPPATH = "weatherPics"
BMPS = {'晴': 'WQING.BMP',
        '阴': 'WYIN.BMP',
        '多云': 'WDYZQ.BMP',
        '小雨': 'WXYU.BMP',
        '中雨': 'WXYU.BMP',
        '雷阵雨': 'WLZYU.BMP'}


def getDuty():
    duty = json.load(open("duty.json"))
    return duty["on"], duty["off"], duty['holiday'], duty["duty"], datetime.strptime(duty["today"], "%Y%m%d").date()


def saveDuty(duty, now):
    dutys = json.load(open("duty.json"))
    dutys["duty"] = duty
    dutys["today"] = now.strftime("%Y%m%d")
    json.dump(dutys, open("duty.json", 'w',
              encoding='utf-8'), ensure_ascii=False)


def printt(*arg):
    print(datetime.now().strftime("%H:%M:%S ")+" ".join([str(x) for x in arg]))


class Citem():
    ifRed = False
    ifChoice = False
    size = 18
    num = ""
    right = ""
    below = ""
    img = ""
    location = ()

    def __str__(self):
        return str(self.num)


def GetCalendar():
    res = []
    ons, offs, holidays, duty, today = getDuty()
    flag = 0
    now = datetime.now()
    for k, v in enumerate(Calendar(6).monthdatescalendar(now.year, now.month)):
        re = []
        for i, j in enumerate(v):
            item = Citem()
            if j.month >= now.month:
                yday = sxtwl.fromSolar(j.year, j.month, j.day)
                item.num = j.day
                item.ifRed = (i == 0 or i == 6)
                if yday.hasJieQi():
                    item.below = jqmc[yday.getJieQi()]
                else:
                    item.below = nlrq[yday.getLunarDay()]
                    if item.below == "初一":
                        item.below = yuefen[yday.getLunarMonth()]
                dayStr = j.strftime("%Y%m%d")
                if dayStr in offs:
                    item.right = "休"
                    item.ifRed = True
                elif dayStr in ons:
                    item.right = "调"
                    item.ifRed = False
                if dayStr[4:] in holidays:
                    item.below = holidays[dayStr[4:]]

                if j == now.date():
                    flag = k
                    item.ifChoice = True
                    nowDate = now.date()
                    if today != nowDate:
                        if not item.ifRed:
                            for i in range((nowDate-today).days):
                                duty.insert(len(duty), duty[0])
                                duty.remove(duty[0])
                        saveDuty(duty, nowDate)

            re.append(item)
        res.append(re)

    if CROW < 5:
        m = int(CROW/2)
        if flag > m:
            res = res[m:]
        else:
            res = res[:flag+m]
    if len(res) > 5:
        res = res[len(res)-5:] if flag > 2 else res[:5-len(res)]

    for i, k in enumerate(res):
        for j, v in enumerate(k):
            if res[i][j].num:
                inter = 9 if res[i][j].num > 9 else 9
                res[i][j].location = (j*RIGHT+inter, (i+2)*DOWN)

    return res


class EDP():
    width = WIDTH
    height = HEIGHT
    batch = 1500
    bit = 10

    def __init__(self, ip="", key=0):
        self._ip = ip
        self._key = key

    def connect(self, ip="", key=0):
        try:
            ws = websocket.WebSocket()
            ws.connect("ws://%s:4280" % ip, header=[
                "sKey: %d" % key])
            self.ws = ws
            self.print("链接EDP成功")
        except Exception as e:
            self.print("链接失败，账户/密码可能有误！")
            print(e)
            return
        return self

    def print(self, *arg):
        printt(*arg)

    def cmd(self, cmd):
        self.ws.send(cmd)
        if self.ws.recv() == "ok":
            return True
        else:
            self.print("操作失败")

    def send(self, args=[]):
        args = args or [0xFF] * self.bits
        for i in range(self.bit):
            self.ws.send_binary(args[self.batch*i:self.batch*(i+1)])
            if self.ws.recv() != "ok":
                self.print("send part: %d fail" % (i+1))
                return False
        return True

    def draw(self, black=[], red=[]):
        if black:
            if self.cmd("init"):
                self.print("发送数据")
                if self.send(black):
                    if red:
                        if self.cmd("next") and self.send(red):
                            self.print("刷新显示")
                            return self.cmd("show")
                    else:
                        self.print("刷新显示")
                        return self.cmd("show")

    def drawCalendar(self, res):
        bimage = Image.new('1', (self.width, self.height), 255)
        rimage = Image.new('1', (self.width, self.height), 255)

        bdraw = ImageDraw.Draw(bimage)
        rdraw = ImageDraw.Draw(rimage)

        bdraw.rectangle((0, DOWN*2 - 18, 400, DOWN*2-4), width=8)
        for i in range(CCOL):
            bdraw.text((i*RIGHT+12, DOWN*2 - 18),
                       TOPNUM[i], fill="white", font=self.getFont(12))
        for re in res:
            for item in re:
                if item.num:
                    font = self.getFont(item.size)
                    numStr = str(item.num)
                    draw = bdraw
                    if item.ifRed:
                        draw = rdraw
                    if item.ifChoice:
                        loc = list(item.location)
                        width, hight = font.getsize(numStr)
                        if item.num < 10:
                            width = 2*width
                            loc[0] -= 5
                        draw.rectangle(
                            (tuple(loc),
                             (loc[0]+width,
                              loc[1]+hight+2)),
                            width=int(hight/2)+2)
                        draw.text(item.location,
                                  numStr,
                                  font=font,
                                  fill="white")
                    else:
                        draw.text(item.location, numStr, font=font)
                    if item.right:
                        loc = (
                            item.location[0]+font.getsize(numStr)[0]+6,
                            item.location[1])
                        width, hight = font.getsize(item.right)
                        rdraw.rectangle(
                            (loc, (loc[0]+width, loc[1]+hight)),
                            width=int(hight/2)+2)
                        rdraw.text(loc,
                                   item.right,
                                   font=font,
                                   fill="white")
                    if item.below:
                        loc = (
                            item.location[0],
                            item.location[1]+font.getsize(numStr)[1]+5)
                        rdraw.text(loc,
                                   item.below,
                                   font=self.getFont(15))
                elif item.img:
                    bimage.paste(Image.open(item.img).resize(
                        (60, 60)), item.location)

        self.draw(self.getbuffer(bimage), self.getbuffer(rimage))

    def getFont(self, size):
        return ImageFont.truetype(FONT, size)

    def getbuffer(self, image):
        buf = [0xFF] * (int(self.width/8) * self.height)
        image = image.convert('1')
        imwidth, imheight = image.size
        pixels = image.load()
        for y in range(imheight):
            for x in range(imwidth):
                if pixels[x, y] == 0:
                    buf[int((x + y * self.width) / 8)
                        ] &= ~(0x80 >> (x % 8))
        return buf

    def getIp(self, name, key):
        printt("查找EDP设备(15S):  "+name)
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_socket.bind(("", 4288))
        now = time.time()
        while time.time() - now < 60:
            receive_data, client = server_socket.recvfrom(1024)
            data = receive_data.decode()
            if data == name:
                printt("获取到EDP设备IP: "+client[0])
                return self.connect(client[0], int(key))
            printt("扫描到设备: "+data)
            time.sleep(1)
        server_socket.close()
        printt("查找EDP设备: 失败! 请检查配置后重新查找")


def GetWeather():
    item = Citem()
    item.location = (180, 4)
    itemPic = Citem()
    itemPic.location = (320, 4)
    try:
        r = requests.get(
            'http://restapi.amap.com/v3/weather/weatherInfo?extensions=all&city=370100&key=64f6fc364b6b427a1b4a4689781b1fa2')
        forecasts = r.json()['forecasts'][0]
        casts = forecasts['casts']
        # item.below = "明日天气："+casts[1]['dayweather']

        weather = casts[0]['dayweather']
        item.num = "天气："+weather
        item.below = "气温：%s - %s度" % (casts[0]['nighttemp'],
                                      casts[0]['daytemp'])
        bmp_name = 'WQING.BMP'
        if weather in BMPS:
            bmp_name = BMPS[weather]
        else:
            if '雨' in weather:
                bmp_name = 'WYU.BMP'
            elif '雪' in weather:
                bmp_name = 'WXUE.BMP'
            elif '雹' in weather:
                bmp_name = 'WBBAO.BMP'
            elif '雾' in weather or '霾' in weather:
                bmp_name = 'WWU.BMP'
            elif '阴' in weather:
                bmp_name = 'WYIN.BMP'
        itemPic.img = os.path.join(BMPPATH, bmp_name)
    except:
        pass

    return [item, itemPic]


def GetDuty():
    dutys = json.load(open("duty.json"))["duty"]

    item = Citem()
    item.location = (10, 4)
    item.size = 25
    item.num = "值日: "
    item.right = dutys[0]
    item.below = "明日:"+dutys[1]
    return item


def GetPic():
    cals = GetCalendar()
    cals.insert(0, [GetDuty(), *GetWeather()])
    return cals


# GetCalendar()
edp = EDP()
if edp.getIp("duty", 8888):
    edp.drawCalendar(GetPic())
