#!/bin/sh
if [ "$GIT_COMMIT" = "97ad4885a03164431ffb7b9dbb1aa49085c66d08" ] || \
   [ "$GIT_COMMIT" = "2f904a5aefdb2bc63bf6bd52e63c639acadc26b0" ] || \
   [ "$GIT_COMMIT" = "b1de40d4717d664a2255ac5bcac517c91c85c613" ]; then
  export GIT_AUTHOR_NAME="VictorPaes28"
  export GIT_AUTHOR_EMAIL="victorpaes2828@gmail.com"
  export GIT_COMMITTER_NAME="VictorPaes28"
  export GIT_COMMITTER_EMAIL="victorpaes2828@gmail.com"
fi
