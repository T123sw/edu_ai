
import os

os.environ['CUDA_VISIBLE_DEVICES'] = '2,3'
from deepsearch import deepsearch_large_llm



if __name__ == '__main__':


    q = input('>>')
    output = deepsearch_large_llm(q)
    print(output)
