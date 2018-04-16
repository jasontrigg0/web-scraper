import argparse
import jtutils
import pandas as pd
import sys
import re

def parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-u","--url")
    parser.add_argument("--css")
    parser.add_argument("-i","--index",type=int)
    parser.add_argument("-t","--table",action="store_true")
    parser.add_argument("-f","--infile",help="html file to read",default=None)
    parser.add_argument("--print_url",action="store_true")
    parser.add_argument("--js",action="store_true",help="load javascript on a page before running")
    parser.add_argument("-g","--grep",help="only keep matches that include a given regex")
    parser.add_argument("--text", action="store_true",help="print the text instead of just the raw html")
    parser.add_argument("--request_info")
    return parser

def internal_args():
    return {"html":None,
            "soup":False, #return the raw soup
            "cookies":{}, "headers":{}, "params":() #http request information
    }


def table2csv(table, print_url=False):
    #possible beautiful soup bug?
    #soup = BeautifulSoup("<table><tr><td></td><td></td><td>stuff</td></tr></table>", 'html.parser')
    #the following two lines don't give the same result:
    #print(list(soup.findAll(["td","th"])))
    #print(list(soup.select("td,th")))
    #using findAll instead of select for this reason

    data_rows = [[process_tag(tag, print_url) for tag in row.findAll(["th","td"])] for row in table.select("tr") if (len(row.select("td")) != 0)]
    row_length = len(data_rows[0])
    #[[process_tag(tag, print_url) for tag in row.select("th")] for row in table.select("tr") if (len(row.select("td")) == 0)]
    all_rows = [[process_tag(tag, print_url) for tag in row.findAll(["th","td"])] for row in table.select("tr")]
    all_rows = [r + ['']*(row_length - len(r)) for r in all_rows]
    return pd.DataFrame.from_records(all_rows, columns=None).to_csv(None, encoding="utf-8", index=False, header=False)

def process_tag(tag, print_url=False):
    anchors = tag.find_all('a')
    if print_url and anchors:
        for tag in anchors:
            if tag.get("href",None):
                return tag["href"]
            else:
                #non href tag
                continue
    else:
        return process_text(tag.text)

def process_text(s):
    if s:
        return s.replace("\r","").replace("\n","").strip()
    else:
        return s

def scrape_table(soup_list, print_url=False):
    for soup in soup_list:
        try:
            yield table2csv(soup,print_url)
        except AssertionError as e:
            sys.stderr.write("WARNING: invalid table. \n")
            sys.stderr.write("Error info: " + str(e) + "\n")
            sys.stderr.write("Skipping table...\n")


def get_href(elt):
    if "href" in getattr(elt,"attrs",[]):
        return elt["href"]
    elif "href" in getattr(elt.parent,"attrs",[]):
        return elt.parent["href"]

def scrape(input_cfg=None):
    cfg = jtutils.process_cfg(input_cfg, parser(), internal_args())
    if cfg["infile"]:
        with open(cfg["infile"]) as f_in:
            soup = jtutils.html_to_soup(f_in.read())
    elif cfg["html"]:
        soup = jtutils.html_to_soup(cfg["html"])
    elif cfg["url"]:
        soup = jtutils.url_to_soup(cfg["url"], cfg["js"], None, cfg["cookies"], cfg["headers"], cfg["params"])
    else:
        raise

    return scrape_soup(soup, cfg)

def scrape_soup(soup, cfg):
    soup_list = []
    if cfg["css"]:
        css = cfg["css"]
        #https://css-tricks.com/attribute-selectors/
        #only support basic single attribute selector for now:
        #a[href="http://aamirshahzad.net"]
        attr_select = re.findall("""^(.*)\[(.*)="(.*)"]$""",css)
        if attr_select:
            if len(attr_select) > 1:
                raise
            tag, attr, val = attr_select[0]
            soup_list = soup.findAll(tag, {attr : val})
            if not soup_list:
                raise Exception("Couldn't find css: " + css)
        else: #use the regular beautiful soup css selector
            soup_list = soup.select(css)
            if not soup_list:
                raise Exception("Couldn't find css: " + css)
    if cfg["table"] and not soup_list:
        soup_list = soup.select("table")
        if not soup_list:
            raise Exception("Couldn't find any tables")

    if not soup_list:
        soup_list = [soup]
    if cfg["grep"]:
        soup_list = [s for s in soup_list if s.find_all(text=re.compile(cfg["grep"]))]
    if cfg["index"] is not None:
        soup_list = [soup_list[cfg["index"]]]
    if cfg["table"]:
        out = list(scrape_table(soup_list, cfg["print_url"]))
        if len(out) == 1:
            return out[0]
        else:
            return out
    else:
        out = ""
        if cfg["soup"]:
            return soup_list
        for soup in soup_list:
            if cfg["print_url"]: #TODO: is this code still used?
                if sys.version_info[0] >= 3:
                    out += (get_href(soup) + '\n')
                else:
                    out += (get_href(soup).encode("utf-8") + '\n')
            elif cfg["text"]:
                if sys.version_info[0] >= 3:
                    out += (soup.text + '\n')
                else:
                    out += (soup.text.encode('utf-8') + '\n')
            else:
                #print raw html
                if sys.version_info[0] >= 3:
                    out += (str(soup) + '\n')
                else:
                    out += (soup.encode("utf-8") + '\n')
        return out
