import multiprocessing as mp
import os
import pandas as pd
import time

from verta import Client


def load_urls():
    urls = [
        'http://s3.amazonaws.com/verta-starter/street-view-images/000001_0.jpg',
        'http://s3.amazonaws.com/verta-starter/street-view-images/000001_1.jpg',
        'http://s3.amazonaws.com/verta-starter/street-view-images/000001_2.jpg',
        'http://s3.amazonaws.com/verta-starter/street-view-images/000001_3.jpg',
        'http://s3.amazonaws.com/verta-starter/street-view-images/000001_4.jpg',
        'http://s3.amazonaws.com/verta-starter/street-view-images/000001_5.jpg',
        'http://s3.amazonaws.com/verta-starter/street-view-images/000002_0.jpg',
        'http://s3.amazonaws.com/verta-starter/street-view-images/000002_1.jpg',
        'http://s3.amazonaws.com/verta-starter/street-view-images/000002_2.jpg',
        'http://s3.amazonaws.com/verta-starter/street-view-images/000002_3.jpg'
    ]
    
    return [[url.strip().split('/')[-1], url.strip()] for url in urls]

def show_metrics(n_urls, n_threads, start_time, end_time):
    total_time = end_time - start_time
    total_time = time.strftime('%Mm %Ss', time.gmtime(total_time))
    
    print(f'URLs processed: {n_urls}.')
    print(f'Threads: {n_threads}.')
    print(f'Total time: {total_time}.')

def show_results(results):
    cols = list(results[0].keys())[:-1]
    cols.extend(list(results[0]['bboxes'].keys()))
    data = []

    for item in results:
        values = list(item.values())[0:3]
        values.extend(list(item['bboxes'].values()))
        data.append(values)

    df = pd.DataFrame(data, columns = cols)
    print(df)

def main():
    VERTA_HOST = 'app.verta.ai'
    ENDPOINT_NAME = 'object-detection-url'

    os.environ['VERTA_EMAIL'] = ''
    os.environ['VERTA_DEV_KEY'] = ''

    client = Client(VERTA_HOST, debug=True)
    endpoint = client.get_or_create_endpoint(ENDPOINT_NAME)
    model = endpoint.get_deployed_model()

    n_threads = int(mp.cpu_count())
    n_urls = 5
    urls = load_urls()[:n_urls]

    start_time = time.time()
    pool = mp.Pool(n_threads)
    map_results = pool.map_async(model.predict, urls, chunksize=1)

    while not map_results.ready():
        print(f"URLs remaining: {map_results._number_left}")
        time.sleep(1.5)

    results = map_results.get()
    pool.close()
    pool.join()
    end_time = time.time()

    show_metrics(n_urls, n_threads, start_time, end_time)
    show_results(results)


if __name__ == '__main__':
    main()
