#!/bin/sh
a=$(git log -1 --format=%an)
if [ "$a" = "Lucca.Dangelo" ]; then
  git commit --amend --author="VictorPaes28 <victorpaes2828@gmail.com>" --no-edit
fi
