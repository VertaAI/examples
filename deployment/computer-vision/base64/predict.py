import base64
import multiprocessing as mp
import numpy as np
import os
import pandas as pd
import time
import json

from verta import Client


def load_imgs(n_imgs):
    path = 'images/'
    files = [file for file in sorted(os.listdir(path))][:n_imgs]
    data = []

    for file in files:
        with open(f"{path}{file}", 'rb') as img:
            img_bytes = base64.b64encode(img.read())
            img_str = img_bytes.decode('utf-8')
            img_str = json.dumps(img_str)
            img_str = np.array(img_str).tolist()
        
        data.append([file, img_str])

    return data

def show_metrics(n_imgs, n_threads, start_time, end_time):
    total_time = end_time - start_time
    total_time = time.strftime('%Mm %Ss', time.gmtime(total_time))
    
    print(f'Images processed: {n_imgs}.')
    print(f'Threads: {n_threads}.')
    print(f'Total time: {total_time}.')

def save_results(results, n_imgs):
    cols = list(results[0].keys())[:-1]
    cols.extend(list(results[0]['bboxes'].keys()))
    data = []

    for item in results:
        values = list(item.values())[0:3]
        values.extend(list(item['bboxes'].values()))
        data.append(values)

    df = pd.DataFrame(data, columns = cols)
    df.to_csv(f"{n_imgs}.csv", index = False)

def main():
    os.environ['VERTA_HOST'] = ''
    os.environ['VERTA_EMAIL'] = ''
    os.environ['VERTA_DEV_KEY'] = ''

    client = Client(os.environ['VERTA_HOST'], debug = True)
    endpoint = client.get_or_create_endpoint('object-detection-v2-base64')
    model = endpoint.get_deployed_model()

    n_threads = int(mp.cpu_count())
    n_imgs = 5000
    imgs = load_imgs(n_imgs)
        
    start_time = time.time()
    pool = mp.Pool(n_threads)
    map_results = pool.map_async(model.predict, imgs, chunksize=1)

    while not map_results.ready():
        print(f"Images remaining: {map_results._number_left}")
        time.sleep(5)

    results = map_results.get()
    pool.close()
    pool.join()
    end_time = time.time()

    show_metrics(n_imgs, n_threads, start_time, end_time)
    save_results(results, n_imgs)


if __name__ == '__main__':
    main()
