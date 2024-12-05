#!/usr/bin/env vpython3
# coding=utf-8
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import metrics_xml_format


class GetMetricsDirTest(unittest.TestCase):
    norm = lambda path: path.replace('/', os.sep)

    def testWithAbsolutePath(self):
        get = metrics_xml_format.GetMetricsDir
        self.assertTrue(get('/src/tools/metrics/actions/abc.xml'))
        self.assertTrue(get('/src/tools/metrics/histograms/abc.xml'))
        self.assertTrue(get('/src/tools/metrics/structured/abc.xml'))
        self.assertTrue(get('/src/tools/metrics/ukm/abc.xml'))

        self.assertFalse(get('/src/tools/metrics/actions/next/abc.xml'))
        self.assertFalse(get('/src/tools/metrics/histograms/next/abc.xml'))
        self.assertFalse(get('/src/tools/metrics/structured/next/abc.xml'))
        self.assertFalse(get('/src/tools/metrics/ukm/next/abc.xml'))

    @mock.patch('os.getcwd', return_value=norm('/abc/tools'))
    def testWithRelativePaths(self, cwd):
        get = metrics_xml_format.GetMetricsDir
        self.assertFalse(get('abc.xml'))
        self.assertTrue(get('metrics/actions/abc.xml'))


class FindMetricsXMLFormatTool(unittest.TestCase):
    norm = lambda path: path.replace('/', os.sep)

    @mock.patch('gclient_paths.GetPrimarySolutionPath',
                return_value=norm('/src'))
    @mock.patch('os.getcwd', return_value=norm('/src'))
    def testWithMetricsXML(self, cwd, solution_path):
        findTool = metrics_xml_format.FindMetricsXMLFormatterTool
        self.assertEqual(
            findTool('tools/metrics/actions/abc.xml'),
            '/src/tools/metrics/actions/pretty_print.py',
        )
        self.assertEqual(
            findTool('/src/tools/metrics/actions/abc.xml'),
            '/src/tools/metrics/actions/pretty_print.py',
        )

    @mock.patch('gclient_paths.GetPrimarySolutionPath',
                return_value=norm('/src'))
    def testWthNonMetricsXML(self, solution_path):
        findTool = metrics_xml_format.FindMetricsXMLFormatterTool
        self.assertEqual(
            findTool('tools/metrics/actions/next/abc.xml'),
            '',
        )

    @mock.patch('gclient_paths.GetPrimarySolutionPath', return_value=None)
    def testWithNonCheckout(self, solution_path):
        findTool = metrics_xml_format.FindMetricsXMLFormatterTool
        self.assertEqual(
            findTool('tools/metrics/actions/abc.xml'),
            '',
        )

    @mock.patch('gclient_paths.GetPrimarySolutionPath',
                return_value=norm('/src'))
    @mock.patch('os.getcwd', return_value=norm('/src'))
    def testWithDifferentCheckout(self, cwd, solution_path):
        findTool = metrics_xml_format.FindMetricsXMLFormatterTool
        self.assertEqual(
            # this is the case the tool was given a file path that is located
            # in a different checkout folder.
            findTool('/different/src/tools/metrics/actions/abc.xml'),
            '',
        )


if __name__ == '__main__':
    unittest.main()
