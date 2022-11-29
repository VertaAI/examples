import multiprocessing as mp
import os
import pandas as pd
import time

from verta import Client


def load_urls():
    with open('urls.txt', 'r') as f:
        return [[line.strip().split('/')[-1], line.strip()] for line in f]

def show_metrics(n_urls, n_threads, start_time, end_time):
    total_time = end_time - start_time
    total_time = time.strftime('%Mm %Ss', time.gmtime(total_time))
    
    print(f'URLs processed: {n_urls}.')
    print(f'Threads: {n_threads}.')
    print(f'Total time: {total_time}.')

def save_results(results, n_urls):
    cols = list(results[0].keys())[:-1]
    cols.extend(list(results[0]['bboxes'].keys()))
    data = []

    for item in results:
        values = list(item.values())[0:3]
        values.extend(list(item['bboxes'].values()))
        data.append(values)

    df = pd.DataFrame(data, columns = cols)
    df.to_csv(f"{n_urls}.csv", index = False)

def main():
    os.environ['VERTA_HOST'] = ''
    os.environ['VERTA_EMAIL'] = ''
    os.environ['VERTA_DEV_KEY'] = ''

    client = Client(os.environ['VERTA_HOST'], debug = True)
    endpoint = client.get_or_create_endpoint('object-detection-v1-url')
    model = endpoint.get_deployed_model()

    n_urls = 10
    n_threads = int(mp.cpu_count())
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
    save_results(results, n_urls)


if __name__ == '__main__':
    main()
