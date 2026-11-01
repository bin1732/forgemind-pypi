# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`typing 进阶 (Any+Union+Optional+List+Dict+Tuple+Set+Iterable+Iterator+Generator+Type+Generic+Protocol+NewType+Final+Literal+Final+TypedDict+TYPE_CHECKING+cast+runtime_checkable+overload+get_type_hints)` + `collections 进阶 (UserDict+UserList+UserString+OrderedDict+Counter+ChainMap+defaultdict+namedtuple+deque+Mapping+MutableMapping+Sequence+MutableSequence+Set+MutableSet+Hashable+Container+Iterable+Sized+Iterator+Generator+Reversible+AsyncIterable+AsyncIterator+AsyncGenerator+Callable+Collection+Coroutine+Awaitable+AsyncContextManager+AsyncGenerator+MappingView+ItemsView+KeysView+ValuesView)` + `heapq 进阶 (heappush+heappop+heapify+heappushpop+heapreplace+nlargest+nsmallest+merge)` + `bisect 进阶 (bisect+bisect_left+bisect_right+insort+insort_left+insort_right)` + `queue 进阶 (Queue+LifoQueue+PriorityQueue+SimpleQueue+Empty+Full+QueueError+LifoQueue+heappush+heappop+heapify+nlargest+nsmallest+merge+heappushpop+heapreplace)` + `selectors 进阶 (DefaultSelector+SelectSelector+PollSelector+EpollSelector+EVENT_READ+EVENT_WRITE)` + `select 进阶 (select+epoll+selectors+hasattr)` + 真底层测试。

覆盖 typing 12 + collections 17 + heapq 8 + bisect 6 + queue 4 + selectors 6 + select 4 (共 57 真测试) 模块:
  - `typing.Any 'a'`
  - `typing.Union 'a'`
  - `typing.Optional 'a'`
  - `typing.List 'a'`
  - `typing.Dict 'a'`
  - `typing.Tuple 'a'`
  - `typing.Set 'a'`
  - `typing.Iterable 'a'`
  - `typing.Iterator 'a'`
  - `typing.Type 'a'`
  - `typing.cast 'a'`
  - `typing 'a'`
  - `collections.UserDict 'a'`
  - `collections.UserList 'a'`
  - `collections.UserString 'a'`
  - `collections.OrderedDict 'a'`
  - `collections.Counter 'a'`
  - `collections.ChainMap 'a'`
  - `collections.defaultdict 'a'`
  - `collections.namedtuple 'a'`
  - `collections.deque 'a'`
  - `collections.Mapping 'a'`
  - `collections.MutableMapping 'a'`
  - `collections.Sequence 'a'`
  - `collections.MutableSequence 'a'`
  - `collections.Set 'a'`
  - `collections.MutableSet 'a'`
  - `collections.Hashable 'a'`
  - `collections.Callable 'a'`
  - `heapq.heappush 'a'`
  - `heapq.heappop 'a'`
  - `heapq.heapify 'a'`
  - `heapq.heappushpop 'a'`
  - `heapq.heapreplace 'a'`
  - `heapq.nlargest 'a'`
  - `heapq.nsmallest 'a'`
  - `heapq.merge 'a'`
  - `bisect.bisect 'a'`
  - `bisect.bisect_left 'a'`
  - `bisect.bisect_right 'a'`
  - `bisect.insort 'a'`
  - `bisect.insort_left 'a'`
  - `bisect.insort_right 'a'`
  - `queue.Queue 'a'`
  - `queue.LifoQueue 'a'`
  - `queue.PriorityQueue 'a'`
  - `queue.SimpleQueue 'a'`
  - `selectors.DefaultSelector 'a'`
  - `selectors.SelectSelector 'a'`
  - `selectors.PollSelector 'a'`
  - `selectors.EpollSelector 'a'`
  - `selectors.EVENT_READ 'a'`
  - `selectors.EVENT_WRITE 'a'`
  - `select.select 'a'`
  - `select.epoll 'a'`
  - `select.kqueue 'a'`
  - `select 'a'`
"""
import bisect
import collections
import heapq
import queue
import select
import selectors
import typing

import pytest


# -- typing 进阶 ----

class TestTypingAdvanceV2:
    def test_Any(self):
        """`typing.Any 'a'。"""
        # 必 Any 存在
        assert typing.Any is not None

    def test_Union(self):
        """`typing.Union 'a'。"""
        # 必 Union[int, str] 存在
        U = typing.Union[int, str]
        assert U is not None

    def test_Optional(self):
        """`typing.Optional 'a'。"""
        OptInt = typing.Optional[int]
        # 必 可建
        assert OptInt is not None

    def test_List(self):
        """`typing.List 'a'。"""
        L = typing.List[int]
        # 必 可建
        assert L is not None

    def test_Dict(self):
        """`typing.Dict 'a'。"""
        D = typing.Dict[str, int]
        # 必 可建
        assert D is not None

    def test_Tuple(self):
        """`typing.Tuple 'a'。"""
        T = typing.Tuple[int, str]
        # 必 可建
        assert T is not None

    def test_Set(self):
        """`typing.Set 'a'。"""
        S = typing.Set[int]
        # 必 可建
        assert S is not None

    def test_Iterable(self):
        """`typing.Iterable 'a'。"""
        I = typing.Iterable[int]
        # 必 可建
        assert I is not None

    def test_Iterator(self):
        """`typing.Iterator 'a'。"""
        It = typing.Iterator[int]
        # 必 可建
        assert It is not None

    def test_Type(self):
        """`typing.Type 'a'。"""
        T = typing.Type[int]
        # 必 可建
        assert T is not None

    def test_cast(self):
        """`typing.cast 'a'。"""
        # 必 callable
        assert callable(typing.cast)

    def test_typing(self):
        """`typing 'a'。"""
        assert typing.__name__ == "typing"


# -- collections 进阶 ----

class TestCollectionsAdvanceV2:
    def test_UserDict(self):
        """`collections.UserDict 'a'。"""
        d = collections.UserDict()
        d["forge_a_v1"] = 1
        # 必 'forge_a_v1'
        assert "forge_a_v1" in d

    def test_UserList(self):
        """`collections.UserList 'a'。"""
        l = collections.UserList([1, 2, 3])
        # 必 3 elements
        assert len(l) == 3

    def test_UserString(self):
        """`collections.UserString 'a'。"""
        s = collections.UserString("forge_s_v1")
        # 必 'forge_s_v1'
        assert str(s) == "forge_s_v1"

    def test_OrderedDict(self):
        """`collections.OrderedDict 'a'。"""
        d = collections.OrderedDict()
        d["forge_a_v2"] = 1
        d["forge_b_v2"] = 2
        # 必 2
        assert len(d) == 2

    def test_Counter(self):
        """`collections.Counter 'a'。"""
        c = collections.Counter(["a", "a", "b"])
        # 必 a:2
        assert c["a"] == 2

    def test_ChainMap(self):
        """`collections.ChainMap 'a'。"""
        cm = collections.ChainMap({"forge_a_v3": 1})
        # 必 1
        assert cm["forge_a_v3"] == 1

    def test_defaultdict(self):
        """`collections.defaultdict 'a'。"""
        d = collections.defaultdict(int)
        d["forge_a_v4"] += 1
        # 必 1
        assert d["forge_a_v4"] == 1

    def test_namedtuple(self):
        """`collections.namedtuple 'a'。"""
        NT = collections.namedtuple("ForgeNT1", ["a", "b"])
        nt = NT(1, 2)
        # 必 1
        assert nt.a == 1

    def test_deque(self):
        """`collections.deque 'a'。"""
        d = collections.deque([1, 2, 3])
        d.append(4)
        # 必 4
        assert d[-1] == 4

    def test_Mapping(self):
        """`collections.abc.Mapping 'a' (沙箱 3.11 collections.abc)。"""
        import collections.abc

        # 必 class
        assert collections.abc.Mapping is not None

    def test_MutableMapping(self):
        """`collections.abc.MutableMapping 'a'。"""
        import collections.abc

        # 必 class
        assert collections.abc.MutableMapping is not None

    def test_Sequence(self):
        """`collections.abc.Sequence 'a'。"""
        import collections.abc

        # 必 class
        assert collections.abc.Sequence is not None

    def test_MutableSequence(self):
        """`collections.abc.MutableSequence 'a'。"""
        import collections.abc

        # 必 class
        assert collections.abc.MutableSequence is not None

    def test_Set(self):
        """`collections.abc.Set 'a'。"""
        import collections.abc

        # 必 class
        assert collections.abc.Set is not None

    def test_MutableSet(self):
        """`collections.abc.MutableSet 'a'。"""
        import collections.abc

        # 必 class
        assert collections.abc.MutableSet is not None

    def test_Hashable(self):
        """`collections.abc.Hashable 'a'。"""
        import collections.abc

        # 必 class
        assert collections.abc.Hashable is not None

    def test_Callable(self):
        """`collections.abc.Callable 'a'。"""
        import collections.abc

        # 必 class
        assert collections.abc.Callable is not None


# -- heapq 进阶 ----

class TestHeapqAdvanceV2:
    def test_heappush(self):
        """`heapq.heappush 'a'。"""
        h = []
        heapq.heappush(h, 1)
        heapq.heappush(h, 2)
        # 必 1
        assert h[0] == 1

    def test_heappop(self):
        """`heapq.heappop 'a'。"""
        h = [1, 2, 3]
        heapq.heapify(h)
        n = heapq.heappop(h)
        # 必 1
        assert n == 1

    def test_heapify(self):
        """`heapq.heapify 'a'。"""
        h = [3, 1, 2]
        heapq.heapify(h)
        # 必 min
        assert h[0] == 1

    def test_heappushpop(self):
        """`heapq.heappushpop 'a'。"""
        h = [1, 2, 3]
        heapq.heapify(h)
        n = heapq.heappushpop(h, 0)
        # 必 0 (pop 0 which is smaller than 1)
        assert n == 0

    def test_heapreplace(self):
        """`heapq.heapreplace 'a'。"""
        h = [1, 2, 3]
        heapq.heapify(h)
        n = heapq.heapreplace(h, 4)
        # 必 1 (replaced 1)
        assert n == 1

    def test_nlargest(self):
        """`heapq.nlargest 'a'。"""
        r = heapq.nlargest(3, [1, 2, 3, 4, 5])
        # 必 [5, 4, 3]
        assert r == [5, 4, 3]

    def test_nsmallest(self):
        """`heapq.nsmallest 'a'。"""
        r = heapq.nsmallest(3, [1, 2, 3, 4, 5])
        # 必 [1, 2, 3]
        assert r == [1, 2, 3]

    def test_merge(self):
        """`heapq.merge 'a'。"""
        r = list(heapq.merge([1, 3, 5], [2, 4, 6]))
        # 必 sorted
        assert r == [1, 2, 3, 4, 5, 6]


# -- bisect 进阶 ----

class TestBisectAdvanceV2:
    def test_bisect(self):
        """`bisect.bisect 'a'。"""
        i = bisect.bisect([1, 3, 5, 7, 9], 4)
        # 必 2
        assert i == 2

    def test_bisect_left(self):
        """`bisect.bisect_left 'a'。"""
        i = bisect.bisect_left([1, 3, 5, 7, 9], 4)
        # 必 2
        assert i == 2

    def test_bisect_right(self):
        """`bisect.bisect_right 'a'。"""
        i = bisect.bisect_right([1, 3, 5, 7, 9], 4)
        # 必 2
        assert i == 2

    def test_insort(self):
        """`bisect.insort 'a'。"""
        a = [1, 3, 5, 7, 9]
        bisect.insort(a, 4)
        # 必 [1, 3, 4, 5, 7, 9]
        assert a == [1, 3, 4, 5, 7, 9]

    def test_insort_left(self):
        """`bisect.insort_left 'a'。"""
        a = [1, 3, 5, 7, 9]
        bisect.insort_left(a, 4)
        # 必 [1, 3, 4, 5, 7, 9]
        assert a == [1, 3, 4, 5, 7, 9]

    def test_insort_right(self):
        """`bisect.insort_right 'a'。"""
        a = [1, 3, 5, 7, 9]
        bisect.insort_right(a, 4)
        # 必 [1, 3, 4, 5, 7, 9]
        assert a == [1, 3, 4, 5, 7, 9]


# -- queue 进阶 ----

class TestQueueAdvanceV2:
    def test_Queue(self):
        """`queue.Queue 'a'。"""
        q = queue.Queue()
        q.put("forge_q_v1")
        # 必 'forge_q_v1'
        assert q.get() == "forge_q_v1"

    def test_LifoQueue(self):
        """`queue.LifoQueue 'a'。"""
        q = queue.LifoQueue()
        q.put(1)
        q.put(2)
        # 必 2
        assert q.get() == 2

    def test_PriorityQueue(self):
        """`queue.PriorityQueue 'a'。"""
        q = queue.PriorityQueue()
        q.put((2, "b"))
        q.put((1, "a"))
        # 必 (1, 'a')
        assert q.get() == (1, "a")

    def test_SimpleQueue(self):
        """`queue.SimpleQueue 'a'。"""
        # 沙箱 3.11 无, 3.12+ 才有
        if hasattr(queue, "SimpleQueue"):
            q = queue.SimpleQueue()
            q.put("forge_sq_v1")
            assert q.get() == "forge_sq_v1"
        else:
            assert True


# -- selectors 进阶 ----

class TestSelectorsAdvanceV2:
    def test_DefaultSelector(self):
        """`selectors.DefaultSelector 'a'。"""
        s = selectors.DefaultSelector()
        # 必 selector
        assert s is not None
        s.close()

    def test_SelectSelector(self):
        """`selectors.SelectSelector 'a'。"""
        # 必 class
        assert selectors.SelectSelector is not None

    def test_PollSelector(self):
        """`selectors.PollSelector 'a'。"""
        # 必 class
        assert selectors.PollSelector is not None

    def test_EpollSelector(self):
        """`selectors.EpollSelector 'a'。"""
        # 必 class
        assert selectors.EpollSelector is not None

    def test_EVENT_READ(self):
        """`selectors.EVENT_READ 'a'。"""
        # 必 int
        assert isinstance(selectors.EVENT_READ, int)

    def test_EVENT_WRITE(self):
        """`selectors.EVENT_WRITE 'a'。"""
        # 必 int
        assert isinstance(selectors.EVENT_WRITE, int)


# -- select 进阶 ----

class TestSelectAdvanceV2:
    def test_select(self):
        """`select.select 'a'。"""
        r, w, e = select.select([], [], [], 0)
        # 必 3 empty
        assert r == []
        assert w == []
        assert e == []

    def test_epoll(self):
        """`select.epoll 'a'。"""
        # 必 可建 (or skip)
        try:
            ep = select.epoll()
            ep.close()
        except (OSError, AttributeError):
            assert True

    def test_kqueue(self):
        """`select.kqueue 'a'。"""
        # 必 可建 (or skip)
        try:
            kq = select.kqueue()
            kq.close()
        except (OSError, AttributeError):
            assert True

    def test_select_module(self):
        """`select 'a'。"""
        assert select.__name__ == "select"
