
import re
import urllib.parse
import sys
import datetime
import win32process
import win32gui
import psutil
import os
import subprocess
import time
from PyQt6.QtGui import QClipboard
from PyQt6 import QtCore
from PyQt6.QtCore import QTimer
from windows_toasts import ToastImageAndText2, WindowsToaster, AudioSource, ToastAudio, ToastDisplayImage, ToastDuration

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def get_foreground_process_name():
    hwnd = win32gui.GetForegroundWindow() 
    _, pid = win32process.GetWindowThreadProcessId(hwnd) 
    proc = psutil.Process(pid) 
    return proc.name()

class ClipboardMonitor:

    def __init__(self, window, app):
        self.window = window
        self.clipboard = app.clipboard()
        self.clipboard.dataChanged.connect(self.clipboardChanged)
        self.previous_clipboard_text = None
        self.last_copy_time = 0

        self.waitForDoubleCopy = QTimer()
        self.waitForDoubleCopy.setSingleShot(True)
        self.waitForDoubleCopy.timeout.connect(self.noDoubleCopy)

        self.tlds = [
            '.com', '.net', '.org', '.jp', '.de', '.uk', '.fr', '.br', '.it', '.ru', 
            '.es', '.me', '.gov', '.pl', '.ca', '.au', '.cn', '.co', '.in', '.nl', 
            '.edu', '.info', '.eu', '.ch', '.id', '.at', '.kr', '.cz', '.mx', '.be', 
            '.tv', '.se', '.tr', '.tw', '.al', '.ua', '.ir', '.vn', '.cl', '.sk', 
            '.ly', '.cc', '.to', '.no', '.fi', '.us', '.pt', '.dk', '.ar', '.hu', 
            '.tk', '.gr', '.il', '.news', '.ro', '.my', '.biz', '.ie', '.za', '.nz', 
            '.sg', '.ee', '.th', '.io', '.xyz', '.pe', '.bg', '.hk', '.rs', '.lt', 
            '.link', '.ph', '.club', '.si', '.site', '.mobi', '.by', '.cat', '.wiki', 
            '.la', '.ga', '.xxx', '.cf', '.hr', '.ng', '.jobs', '.online', '.kz', 
            '.ug', '.gq', '.ae', '.is', '.lv', '.pro', '.fm', '.tips', '.ms', '.sa', '.app'
            ]
        
        self.road_indicators = [
            "Street", "St",
            "Avenue", "Ave", 
            "Road", "Rd",
            "Highway", "Hwy",
            "Plaza", "Pl", 
            "Court", "Ct", 
            "Boulevard", "Blvd", 
            "Drive", "Dr",
            "Lane", "Ln",
            "Terrace", "Ter",
            "Place", "Pl",
            "Circle", "Cir",
            "Alley", "Aly",
            "Crescent", "Cres",
            "Way", "Wy",
            "Trail", "Trl",
            "Parkway", "Pkwy",
            "Square", "Sq",
            "Loop", "Lp",
            "Path",
            "Pike",
            "Freeway", "Fwy",
            "Expressway", "Expy",
            "Route", "Rte",
            "Interstate", "I-",
            "Turnpike", "Tpke",
            "Junction", "Jct",
            "Extension", "Ext",
            "Crossing", "Xing",
            "Run",
            "Point", "Pt",
            "Branch", "Br",
            "Grove", "Grv",
            "Manor", "Mnr",
            "Ridge", "Rdg",
            "Hollow", "Holw",
            "Gate", "Gt",
            "Vista", "Vis",
            "Hill", "Hl",
            "Green", "Grn",
            "Valley", "Vly"
        ]

        
        self.direction_indicators = ["N", "S", "E", "W", "NE", "NW", "SE", "SW"]
        
        self.state_province_territory = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", 
            "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", 
            "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", 
            "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
            "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC", 
            "AS", "GU", "MP", "PR", "UM", "VI", "AB", "BC", "MB", "NB", "NL", 
            "NS", "ON", "PE", "QC", "SK", "NT", "NU", "YT"]


        self.airline_codes = ['AA', 'UA', 'WN', 'DL', 'AS', 'NK', 'B6', 'HA', 'AC', 'WS', 
                        'AF', 'KL', 'BA', 'EI', 'IB', 'AZ', 'LH', 'EW', 'FR', 'U2', 
                        'TK', 'SU', 'EK', 'EY', 'QR', 'CX', 'HKA', 'NH', 'JL', 'QF',
                        'VA', 'NZ', 'SA', 'ET', 'RJ', 'KQ', 'AT', 'HR', 'G3', 'JJ',
                        'LA', 'AM', 'AV', 'CM', 'TA', 'SG', 'AI', 'MU', 'CZ', 'KE']

        self.airline_names = ['American', 'United', 'Southwest', 'Delta', 'Alaska', 'Spirit', 'JetBlue', 'Hawaiian', 
                        'Air Canada', 'WestJet', 'Air France', 'KLM', 'British Airways', 'Aer Lingus', 
                        'Iberia', 'Alitalia', 'Lufthansa', 'Eurowings', 'Ryanair', 'EasyJet', 
                        'Turkish', 'Aeroflot', 'Emirates', 'Etihad', 'Qatar', 'Cathay Pacific', 
                        'Hong Kong', 'All Nippon', 'Japan', 'Qantas',
                        'Virgin Australia', 'Air New Zealand', 'South African', 'Ethiopian', 
                        'Royal Jordanian', 'Kenya', 'Royal Air Maroc', 'Hahn Air', 'Gol Linhas Aereas', 
                        'LATAM Airlines Brasil', 'LATAM Airlines Chile', 'Aeromexico', 'Avianca', 'Copa', 
                        'TACA', 'SpiceJet', 'Air India', 'China Eastern', 'China Southern', 'Korean Air']

        self.airline_suffixes = ['airline', 'airlines', 'airway', 'airways', 'air']

    def clipboardChanged(self):
        current_time = time.time()
        if self.clipboard.text() == self.previous_clipboard_text:
            if current_time - self.last_copy_time < 0.25:
                self.waitForDoubleCopy.stop()
                self.processClipboard(True)
            else:
                self.last_copy_time = current_time
                return
        else:
            self.waitForDoubleCopy.start(300)
 
        self.last_copy_time = current_time
        self.previous_clipboard_text = self.clipboard.text()

    def noDoubleCopy(self):
        self.processClipboard(False)

    def processClipboard(self, copyAndGo):

        isFirefox = get_foreground_process_name() in ['firefox.exe', 'firefox_go.exe']

        parsedClipboard = self.parseClipboard()
        matchType = None
        displayText = None
        url = None

        if parsedClipboard["tracking_number"]:
            matchType = parsedClipboard["tracking_number"]["shipper"] + " tracking number"
            displayText = parsedClipboard["tracking_number"]["tracking_number"]
            url = parsedClipboard["tracking_number"]["url"]
        elif parsedClipboard["flight_number"]:
            matchType = "flight number"
            displayText = parsedClipboard["flight_number"]["flight_number"]
            url = parsedClipboard["flight_number"]["url"]
        elif parsedClipboard["address"]:
            matchType = "address"
            displayText = parsedClipboard["address"]["address"]
            url = parsedClipboard["address"]["url"]
        elif parsedClipboard["url"]:
            matchType = "link"
            displayText = parsedClipboard["url"]
            url = parsedClipboard["url"]
        elif parsedClipboard["searchText"]:
            matchType = "search query"
            displayText = parsedClipboard["searchText"]
            url = parsedClipboard["google_search_url"]
        else:
            return

        if copyAndGo and self.window.settings.value("copy_and_go", type=bool):
            subprocess.call(f'explorer "{url}"', shell=True)
            self.copy_and_go = False
            return

        if matchType and matchType != "search query" and not (isFirefox and matchType == "link") and self.window.settings.value("clipboard_notifications", True, type=bool):
            toaster = WindowsToaster("Firefox Go")

            newToast = ToastImageAndText2()
            newToast.SetAudio(ToastAudio(AudioSource.Default, False, True))
            newToast.SetDuration(ToastDuration.Short)
            newToast.SetExpirationTime(datetime.datetime.now())
            newToast.SetHeadline("Do you want to open this " + matchType + " in Firefox?")
            newToast.SetFirstLine(displayText) # type: ignore
            newToast.AddImage(ToastDisplayImage.fromPath(resource_path("images/firefox.png")))
            newToast.on_activated = lambda _: subprocess.call(f'explorer "{url}"', shell=True) # type: ignore
            toaster.show_toast(newToast)
    
        if self.window.settings.value("clipboard_enabled", type=bool):
            self.window.clipboardUpdated(matchType, displayText, url)

    def parseClipboard(self):

        text = self.clipboard.text()
        print(f"Clipboard content updated: {text}")
        tokens = text.split()

        url = self.extract_url(text)
        print("URL found:", url)

        if len(tokens) <= 10 and len(tokens) > 0 and len(text) <= 100:
            searchText = text
            google_search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(text)}"
        else:
            searchText = None
            google_search_url = None

        print("Google search URL:", google_search_url)

        tracking_number = self.extract_tracking_number(text)
        print("Tracking numbers found:", tracking_number)

        address = self.extract_address(text)
        print("Address found:", address)

        flight_number = self.extract_flight_number(text)
        print("Flight number found:", flight_number)

        parsedClipboard = {
            'searchText': searchText, 
            'google_search_url': google_search_url, 
            'url': url, 
            'tracking_number': tracking_number, 
            'address': address, 
            'flight_number': flight_number, 
        }

        return parsedClipboard

    def extract_url(self, text):

        url = ""
        tlds = [re.escape(tld) for tld in self.tlds] # Escape regex characters
        tld_string = '|'.join(tlds) # Join TLDs with '|'
        pattern = re.compile(r'(?<=\w)(?:' + tld_string + r')(?=\W|$)') 
        match = pattern.search(text)
        if match is not None:
            url = match.group(0)
            domain = text[:match.start()]
            for i, char in enumerate(domain[::-1]):
                if not char.isalnum() and char != '.':
                    domain = domain[::-1][:i][::-1] 
                    break
                elif char == '.' and not domain[::-1][i+1].isalnum():
                    domain = domain[::-1][:i][::-1] 
                    break
            url = domain + url

            url_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~:/?#[]@!$&\'()*+,;=%')
            for i, char in enumerate(text[match.end():]):
                if char not in url_chars:
                    url = url + text[match.end():match.end()+i]
                    break
            else:
                url = url + text[match.end():]
        
        if url and not url.startswith("http"):
            url = "https://" + url

        return url
        
    def extract_tracking_number(self, text):
        tracking_number = None

        text = re.sub(r'[-\s]', '', text)
        text = text.upper()

        if re.match(r'^(1Z[A-Z0-9]{16}|MI[A-Z0-9]{17})$', text):
            tracking_number = {'shipper':"UPS", 'tracking_number':text, 'url':f"https://www.google.com/search?q={text}"}
        elif re.match(r'^(H\d{10}|\d{12})$', text):
            tracking_number = {'shipper':"FedEx", 'tracking_number':text, 'url':f"https://www.google.com/search?q={text}"}
        elif re.match(r'^(\d{20,22}|[A-Z]{2}\d{9}US|82\d{8})$', text):
            tracking_number = {'shipper':"USPS", 'tracking_number':text, 'url':f"https://www.google.com/search?q={text}"}
        elif re.match(r'^(GM|LE|EE|CP|JJD|JVGL)[A-Z0-9]{9,33}$|\d{10}$', text):
            tracking_number = {'shipper':"DHL", 'tracking_number':text, 'url':f"https://www.google.com/search?q={text}"}
        
        return tracking_number


    def extract_address(self, text):
        addressObject = None
        
        text = re.sub(r"[^\w\s.,'&#-]", "", text)
        tokens = text.split()
        
        i = 0
        while i < len(tokens) and not addressObject:
            token = tokens[i]

            if re.match(r'^\d{1,6}\S{0,3}$', token):
                possibleAddress = [token]
                i += 1

                for j in range(i, min(i+5, len(tokens))):
                    possibleAddress.append(tokens[j])
                    if any(tokens[j].lower() == indicator.lower() for indicator in self.road_indicators):
                        i = j+1
                        break
                else:
                    i += 1
                    continue
                
                address = ' '.join(possibleAddress)

                if i < len(tokens) and any(tokens[i].lower() == indicator.lower() for indicator in self.direction_indicators):
                    possibleAddress.append(tokens[i])
                    address = ' '.join(possibleAddress)
                    i += 1

                for j in range(i, min(i+4, len(tokens))):
                    possibleAddress.append(tokens[j])
                    if any(tokens[j].lower() == indicator.lower() for indicator in self.state_province_territory):
                        i = j+1
                        break
                else:
                    addressObject = {'address': address, 'url': f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(address)}"}
                    i += 1
                    continue
                
                if i < len(tokens):
                    if re.match(r'^\d{5}$', tokens[i], re.IGNORECASE) or \
                    re.match(r'^\d{5}-\d{4}$', tokens[i], re.IGNORECASE) or \
                    re.match(r'^[A-Z]\d[A-Z]\d[A-Z]\d$', tokens[i], re.IGNORECASE):
                        possibleAddress.append(tokens[i])
                    elif (re.match(r'^[A-Z]\d[A-Z]$', tokens[i], re.IGNORECASE) and re.match(r'^\d[A-Z]\d$', tokens[i+1], re.IGNORECASE)):
                        possibleAddress.append(tokens[i])
                        possibleAddress.append(tokens[i+1])
                        
                address = ' '.join(possibleAddress)
                addressObject = {'address': address, 'url': f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(address)}"}
            else:
                i += 1

        return addressObject

    def extract_flight_number(self, text):

        text = re.sub(r'[^\w\s-]', '', text)
        tokens = re.split(r'[-\s]', text)

        flightNumberObject = None
        pattern = re.compile(r"([A-Za-z]+)(\d+)")

        for token in tokens:
            match = pattern.match(token)
            if match:
                airline_code, flightNumber = match.groups()
                if airline_code.upper() in self.airline_codes:
                    appendFlightNumber = airline_code + flightNumber
                    flightNumberObject = {'flight_number': appendFlightNumber, 'url': f"https://www.google.com/search?q={urllib.parse.quote_plus(appendFlightNumber)}"}
                    return flightNumberObject

        for i in range(len(tokens) - 1): 
            if tokens[i].upper() in self.airline_codes:
                if tokens[i+1].isdigit():
                    appendFlightNumber = ' '.join(tokens[i:i+2])
                    flightNumberObject = {'flight_number': appendFlightNumber, 'url': f"https://www.google.com/search?q={urllib.parse.quote_plus(appendFlightNumber)}"}
            elif any(' '.join(tokens[i:i+len(name.split())]).lower() == name.lower() for name in self.airline_names):
                name_length = len([name for name in self.airline_names if ' '.join(tokens[i:i+len(name.split())]) == name][0].split())
                if i + name_length < len(tokens) and tokens[i + name_length].isdigit():
                    appendFlightNumber = ' '.join(tokens[i:i+name_length+1])
                    flightNumberObject = {'flight_number': appendFlightNumber, 'url': f"https://www.google.com/search?q={urllib.parse.quote_plus(appendFlightNumber)}"}
                elif i + name_length + 1 < len(tokens) and tokens[i + name_length].lower() in self.airline_suffixes and tokens[i + name_length + 1].isdigit():
                    appendFlightNumber = ' '.join(tokens[i:i+name_length+2])
                    flightNumberObject = {'flight_number': appendFlightNumber, 'url': f"https://www.google.com/search?q={urllib.parse.quote_plus(appendFlightNumber)}"}

            if flightNumberObject:
                break

        return flightNumberObject


