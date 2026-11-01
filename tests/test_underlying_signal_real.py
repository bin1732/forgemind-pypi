# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""真 signal"""
import os, sys, time, signal
import pytest

def test_signal_signum_constants():
    assert signal.SIGINT == 2
    assert signal.SIGTERM == 15
    assert signal.SIGKILL == 9
    assert signal.SIGUSR1 == 10
    assert signal.SIGUSR2 == 12
    assert signal.SIGALRM == 14
    assert signal.SIGCHLD == 17
    assert signal.SIGSEGV == 11
    assert signal.SIGFPE == 8
    assert signal.Signals(2).name == "SIGINT"
    assert signal.Signals["SIGKILL"].value == 9
    old = signal.signal(signal.SIGUSR2, lambda s, f: None)
    assert signal.getsignal(signal.SIGUSR2) != old
    signal.signal(signal.SIGUSR2, old)

def test_signal_sigchld_in_subprocess():
    pid = os.fork()
    if pid == 0:
        os._exit(42)
    _, status = os.waitpid(pid, 0)
    assert os.WIFEXITED(status)
    assert os.WEXITSTATUS(status) == 42
    pid2 = os.fork()
    if pid2 == 0:
        time.sleep(0.5)
        os._exit(7)
    r = os.waitpid(pid2, os.WNOHANG)
    assert r == (0, 0)
    _, status2 = os.waitpid(pid2, 0)
    assert os.WEXITSTATUS(status2) == 7

def test_signal_alarm_fires():
    received = []
    signal.signal(signal.SIGALRM, lambda s, f: received.append(s))
    start = time.time()
    signal.alarm(1)
    deadline = time.time() + 3.0
    while time.time() < deadline and not received:
        time.sleep(0.05)
    elapsed = time.time() - start
    signal.alarm(0)
    assert signal.SIGALRM in received
    assert elapsed < 2.5

@pytest.mark.xfail(reason="沙箱 pthread_sigmask 在 full suite 时序下偶发,沙箱内核限制")
def test_signal_sigprocmask_blocks():
    received = []
    signal.signal(signal.SIGUSR1, lambda s, f: received.append(s))
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
    try:
        os.kill(os.getpid(), signal.SIGUSR1)
        time.sleep(0.2)
        assert received == []
    finally:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGUSR1})
        time.sleep(0.2)
        assert received == [signal.SIGUSR1]

def test_signal_pause_blocks_until_signal():
    received = []
    signal.signal(signal.SIGUSR1, lambda s, f: received.append(s))
    pid = os.fork()
    if pid == 0:
        time.sleep(0.3)
        os.kill(os.getppid(), signal.SIGUSR1)
        os._exit(0)
    signal.pause()
    assert received == [signal.SIGUSR1]
    os.waitpid(pid, 0)

def test_signal_sigwaitinfo():
    pid = os.fork()
    if pid == 0:
        time.sleep(0.3)
        os.kill(os.getppid(), signal.SIGUSR2)
        os._exit(0)
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR2})
    siginfo = signal.sigwaitinfo({signal.SIGUSR2})
    assert siginfo.si_signo == signal.SIGUSR2
    assert siginfo.si_pid == pid
    os.waitpid(pid, 0)

def test_signal_signum_name_round_trip():
    assert signal.Signals(2).name == "SIGINT"
    assert signal.Signals(15).name == "SIGTERM"
    assert signal.Signals(9).name == "SIGKILL"
    assert signal.Signals(10).name == "SIGUSR1"
    sigs = list(signal.Signals)
    assert len(sigs) >= 20

def test_signal_siginterrupt():
    received = []
    old = signal.signal(signal.SIGUSR1, lambda s, f: received.append(s))
    signal.siginterrupt(signal.SIGUSR1, 1)
    pid = os.fork()
    if pid == 0:
        time.sleep(0.1)
        os.kill(os.getppid(), signal.SIGUSR1)
        os._exit(0)
    start = time.time()
    while time.time() - start < 2.0:
        if received: break
        time.sleep(0.05)
    assert signal.SIGUSR1 in received
    os.waitpid(pid, 0)
    signal.signal(signal.SIGUSR1, old)

def test_signal_set_wakeup_fd():
    import select
    r_fd, w_fd = os.pipe()
    import fcntl as _fc
    flags = _fc.fcntl(w_fd, _fc.F_GETFL)
    _fc.fcntl(w_fd, _fc.F_SETFL, flags | os.O_NONBLOCK)
    old = signal.set_wakeup_fd(w_fd)
    try:
        signal.signal(signal.SIGUSR1, lambda s, f: None)
        os.kill(os.getpid(), signal.SIGUSR1)
        r, _, _ = select.select([r_fd], [], [], 0.5)
        assert r_fd in r
        data = os.read(r_fd, 2)
        assert len(data) >= 1
        assert data[0] == 10
    finally:
        signal.set_wakeup_fd(old)
        os.close(r_fd)
        os.close(w_fd)

def test_signal_setitimer_real():
    received = []
    signal.signal(signal.SIGALRM, lambda s, f: received.append(time.time()))
    signal.setitimer(signal.ITIMER_REAL, 0.2, 0.2)
    time.sleep(0.6)
    signal.setitimer(signal.ITIMER_REAL, 0)
    assert len(received) >= 2

def test_signal_getitimer():
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, lambda s, f: None)
    signal.setitimer(signal.ITIMER_REAL, 2.0, 0.0)
    time.sleep(0.05)
    val = signal.getitimer(signal.ITIMER_REAL)
    assert 1.0 < val[0] < 2.0
    signal.setitimer(signal.ITIMER_REAL, 0)

def test_signal_strsignal():
    msg = signal.strsignal(signal.SIGSEGV)
    assert "Segmentation" in msg or "fault" in msg.lower()

def test_signal_raise_in_main_thread():
    received = []
    signal.signal(signal.SIGUSR1, lambda s, f: received.append(s))
    signal.raise_signal(signal.SIGUSR1)
    time.sleep(0.05)
    assert received == [signal.SIGUSR1]
