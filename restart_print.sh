#!/usr/bin/env bash

PRINTSTATUS=$(lpstat -u |awk '{ print $1;}')

JOBID="$(cut -d '-' -f2 <<<$PRINTSTATUS)"


lp -i $JOBID  -H resume
echo $JOBID 
echo $PRINTSTATUS

