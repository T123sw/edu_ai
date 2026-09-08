"""Check the two algorithm contracts used in the outline's review feedback.

This validates the specified algorithms, not arbitrary generated prose.
"""
from bisect import bisect_left
from itertools import combinations_with_replacement
import json


def match(a, x):
    n=len(a)
    l,r=0,n-1
    while True:
        assert 0 <= l <= r+1 <= n
        assert all(v<x for v in a[:l]) and all(v>x for v in a[r+1:])
        if l>r:
            return -1
        size=r-l+1
        m=(l+r)//2
        if a[m]==x:
            return m
        if a[m]<x:
            l=m+1
        else:
            r=m-1
        assert r-l+1 < size


def left(a, x):
    n=len(a)
    l,r=0,n
    while True:
        assert 0 <= l <= r <= n
        assert all(v<x for v in a[:l]) and all(v>=x for v in a[r:])
        if l==r:
            return l
        size=r-l
        m=(l+r)//2
        if a[m]<x:
            l=m+1
        else:
            r=m
        assert r-l < size


if __name__=='__main__':
    cases=0
    for n in range(7):
        for a in combinations_with_replacement(range(4), n):
            for x in range(-1,5):
                found=match(a,x)
                assert (found==-1 and x not in a) or (0<=found<len(a) and a[found]==x)
                ip=left(a,x)
                assert ip==bisect_left(a,x)
                assert (ip<len(a) and a[ip]==x)==(x in a)
                cases+=1
    print(json.dumps({'passed':True,'input_target_pairs':cases,'algorithms':2,
                      'checks':['invariant_each_iteration_and_exit','strict_shrink','return_contract','safe_membership_check']}))
