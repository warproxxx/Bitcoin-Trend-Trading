import pandas as pd
import requests
import os
import datetime
import shutil
from glob import glob
import numpy as np
import datetime

coins = ['ETH', 'XBT']

#1) Download
def download_file(name):
    try:
        print(name)
        url = "https://s3-eu-west-1.amazonaws.com/public.bitmex.com/data/trade/{}".format(name)

        r = requests.get(url)

        if not(os.path.isdir("data/")):
            os.mkdir("data/")

        with open('data/{}'.format(name), 'wb') as f:
            f.write(r.content)
    except Exception as e:
        print("Error: {} in {}".format(str(e), name))


current = pd.to_datetime("1970-01-01").date()

for coin in coins:
    now = pd.to_datetime(pd.read_csv('features/{}/priced_features.csv'.format(coin)).iloc[-1]['timestamp']).date()
    current = max(current, now)

start_date = current + datetime.timedelta(days=1)
end_date = datetime.datetime.utcnow().date() - datetime.timedelta(days=1)

while start_date <= end_date:
    download_file(start_date.strftime("%Y%m%d.csv.gz"))
    start_date += datetime.timedelta(days=1)

#2) Extract and Combine

all_files = [file for file in glob("data/*")  if ".gz" in file] #sort by date
all_files.sort()
print(all_files)

curr_files = {}

for file in all_files: 
    print(file)    
    try:
        data = pd.read_csv(file, compression='gzip')
        curr_date = file.split("/")[-1].replace(".csv.gz", "")
        
        for g in data.groupby('symbol'):
            symbol = g[0]
            op_dir = "processed/{}/trades/".format(symbol[:3])
            
            if not(os.path.isdir(op_dir)):
                os.makedirs(op_dir)
            
            if symbol in curr_files:
                mb_size = os.stat(curr_files[symbol]).st_size * 0.000001
                if mb_size > 10240: 
                    curr_files[symbol] = op_dir + "{}_{}.csv".format(symbol, curr_date)
            else:
                curr_files[symbol] = curr_files[symbol] = op_dir + "{}_{}.csv".format(symbol, curr_date)
                    
            if os.path.isfile(curr_files[symbol]):
                g[1].to_csv(curr_files[symbol], index=None, mode='a', header=None)
            else:
                g[1].to_csv(curr_files[symbol], index=None)
    except:
        pass
            
    os.remove(file)

#3) Get Significant Trades
for coin in coins:
    files = [f for f in glob("processed/{}/trades/*".format(coin)) if f.split("/")[-1][:7] == "{}USD_".format(coin)]
    files.sort()

    for file in files:
        f = file.split("_")[-1].replace(".csv", "")

        print(file)
        df = pd.read_csv(file)
        df = df[['timestamp', 'side', 'homeNotional', 'foreignNotional']]
        df = df.groupby(['timestamp', 'side']).sum() 
        df = df.reset_index()
        df = df[df['foreignNotional'] > 500]
        df['timestamp'] = pd.to_datetime(df['timestamp'], format="%Y-%m-%dD%H:%M:%S.%f")
        df['price'] = df['foreignNotional']/df['homeNotional']

        op_file = 'processed/{}/significant_trades/{}_significant_trades_{}.csv'.format(coin, coin, f)

        if not os.path.isfile(op_file):
            df.to_csv(op_file, index=None)
        else:
            df.to_csv(op_file, index=None, mode='a', header=None)

        df = pd.read_csv(op_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        df = df.drop_duplicates()
        df.to_csv(op_file, index=None) #can save as csv.gz here if size is too big

        os.remove(file)
