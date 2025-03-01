#! /usr/bin/env python3

import argparse
import atexit
import os
import subprocess
import signal
import sys
import time
import unittest

from test_device import (
    Bitcoind,
    DeviceEmulator,
    DeviceTestCase,
    TestDeviceConnect,
    TestDisplayAddress,
    TestGetKeypool,
    TestGetDescriptors,
    TestSignMessage,
    TestSignTx,
)

from hwilib._cli import process_commands

class LedgerEmulator(DeviceEmulator):
    def __init__(self, path):
        self.emulator_path = path
        self.emulator_proc = None
        self.emulator_stderr = None
        self.emulator_stdout = None
        try:
            os.unlink('ledger-emulator.stderr')
        except FileNotFoundError:
            pass
        self.type = "ledger"
        self.path = 'tcp:127.0.0.1:9999'
        self.fingerprint = 'f5acc2fd'
        self.master_xpub = 'xpub6Cak8u8nU1evR4eMoz5UX12bU9Ws5RjEgq2Kq1RKZrsEQF6Cvecoyr19ZYRikWoJo16SXeft5fhkzbXcmuPfCzQKKB9RDPWT8XnUM62ieB9'
        self.password = ""
        self.supports_ms_display = False
        self.supports_xpub_ms_display = False
        self.supports_unsorted_ms = False
        self.supports_taproot = False
        self.strict_bip48 = True

    def start(self):
        super().start()
        automation_path = os.path.abspath("data/speculos-automation.json")

        self.emulator_stderr = open('ledger-emulator.stderr', 'a')
        # Start the emulator
        self.emulator_proc = subprocess.Popen(['python3', './' + os.path.basename(self.emulator_path), '--display', 'headless', '--automation', 'file:{}'.format(automation_path), '--log-level', 'automation:DEBUG', '--log-level', 'seproxyhal:DEBUG', '--api-port', '0', './apps/btc.elf'], cwd=os.path.dirname(self.emulator_path), stderr=self.emulator_stderr, preexec_fn=os.setsid)
        # Wait for simulator to be up
        while True:
            try:
                enum_res = process_commands(['enumerate'])
                found = False
                for dev in enum_res:
                    if dev['type'] == 'ledger' and 'error' not in dev:
                        found = True
                        break
                if found:
                    break
            except Exception as e:
                print(str(e))
                pass
            time.sleep(0.5)
        atexit.register(self.stop)

    def stop(self):
        super().stop()
        if self.emulator_proc.poll() is None:
            os.killpg(os.getpgid(self.emulator_proc.pid), signal.SIGTERM)
            os.waitpid(self.emulator_proc.pid, 0)
        if self.emulator_stderr is not None:
            self.emulator_stderr.close()
        if self.emulator_stdout is not None:
            self.emulator_stdout.close()
        atexit.unregister(self.stop)

# Ledger specific disabled command tests
class TestLedgerDisabledCommands(DeviceTestCase):
    def test_pin(self):
        result = self.do_command(self.dev_args + ['promptpin'])
        self.assertIn('error', result)
        self.assertIn('code', result)
        self.assertEqual(result['error'], 'The Ledger Nano S and X do not need a PIN sent from the host')
        self.assertEqual(result['code'], -9)

        result = self.do_command(self.dev_args + ['sendpin', '1234'])
        self.assertIn('error', result)
        self.assertIn('code', result)
        self.assertEqual(result['error'], 'The Ledger Nano S and X do not need a PIN sent from the host')
        self.assertEqual(result['code'], -9)

    def test_setup(self):
        result = self.do_command(self.dev_args + ['-i', 'setup'])
        self.assertIn('error', result)
        self.assertIn('code', result)
        self.assertEqual(result['error'], 'The Ledger Nano S and X do not support software setup')
        self.assertEqual(result['code'], -9)

    def test_wipe(self):
        result = self.do_command(self.dev_args + ['wipe'])
        self.assertIn('error', result)
        self.assertIn('code', result)
        self.assertEqual(result['error'], 'The Ledger Nano S and X do not support wiping via software')
        self.assertEqual(result['code'], -9)

    def test_restore(self):
        result = self.do_command(self.dev_args + ['-i', 'restore'])
        self.assertIn('error', result)
        self.assertIn('code', result)
        self.assertEqual(result['error'], 'The Ledger Nano S and X do not support restoring via software')
        self.assertEqual(result['code'], -9)

    def test_backup(self):
        result = self.do_command(self.dev_args + ['backup'])
        self.assertIn('error', result)
        self.assertIn('code', result)
        self.assertEqual(result['error'], 'The Ledger Nano S and X do not support creating a backup via software')
        self.assertEqual(result['code'], -9)

class TestLedgerGetXpub(DeviceTestCase):
    def test_getxpub(self):
        result = self.do_command(self.dev_args + ['--expert', 'getxpub', 'm/44h/0h/0h/3'])
        self.assertEqual(result['xpub'], "tpubDED6QbjWtz9KiBmvw9A73bdQpqdZhCUd6LXMM1NChthDvPVao2M9XogGQdnk1zg67KLeQ2hkGMujDuDX3H2vQCwCRenwW81gGJnp3W5kteV")
        self.assertTrue(result['testnet'])
        self.assertFalse(result['private'])
        self.assertEqual(result['depth'], 4)
        self.assertEqual(result['parent_fingerprint'], '2930ce56')
        self.assertEqual(result['child_num'], 3)
        self.assertEqual(result['chaincode'], 'a3cd503ab3ffd3c31610a84307f141528c7e9b8416e10980ced60d1868b463e2')
        self.assertEqual(result['pubkey'], '03d5edb7c091b5577e1e2e6493b34e602b02547518222e26472cfab1745bb5977d')

def ledger_test_suite(emulator, bitcoind, interface):
    dev_emulator = LedgerEmulator(emulator)

    signtx_cases = [
        (["legacy"], ["legacy"], True, True),
        (["segwit"], ["segwit"], True, True),
    ]

    # Generic Device tests
    suite = unittest.TestSuite()
    suite.addTest(DeviceTestCase.parameterize(TestLedgerDisabledCommands, bitcoind, emulator=dev_emulator, interface=interface))
    suite.addTest(DeviceTestCase.parameterize(TestLedgerGetXpub, bitcoind, emulator=dev_emulator, interface=interface))
    suite.addTest(DeviceTestCase.parameterize(TestDeviceConnect, bitcoind, emulator=dev_emulator, interface=interface, detect_type=dev_emulator.type))
    suite.addTest(DeviceTestCase.parameterize(TestGetDescriptors, bitcoind, emulator=dev_emulator, interface=interface))
    suite.addTest(DeviceTestCase.parameterize(TestGetKeypool, bitcoind, emulator=dev_emulator, interface=interface))
    suite.addTest(DeviceTestCase.parameterize(TestDisplayAddress, bitcoind, emulator=dev_emulator, interface=interface))
    suite.addTest(DeviceTestCase.parameterize(TestSignMessage, bitcoind, emulator=dev_emulator, interface=interface))
    suite.addTest(DeviceTestCase.parameterize(TestSignTx, bitcoind, emulator=dev_emulator, interface=interface, signtx_cases=signtx_cases))

    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    return result.wasSuccessful()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test Ledger implementation')
    parser.add_argument('emulator', help='Path to the ledger emulator')
    parser.add_argument('bitcoind', help='Path to bitcoind binary')
    parser.add_argument('--interface', help='Which interface to send commands over', choices=['library', 'cli', 'bindist'], default='library')

    args = parser.parse_args()

    # Start bitcoind
    bitcoind = Bitcoind.create(args.bitcoind)

    sys.exit(not ledger_test_suite(args.emulator, bitcoind, args.interface))
