#!/usr/bin/env bash

type coverage >/dev/null 2>&1
if [ $? -ne 0 ]; then
  echo coverage is not installed.  please install and try again.
  exit 1
fi

coverage run run.py
coverage report -m
