Запуск программы производится командой 

./full-episkops-parser ../input.xml output.json

или с компиляцией через систему сборки cabal

cd ..
cabal run full-episkops-parser -- input.xml output.json

или после выполнения cabal build

./dist-newstyle/build/x86_64-linux/ghc-9.4.7/full-episkops-parser-0.1.0.0/x/full-episkops-parser/build/full-episkops-parser/full-episkops-parser \
input.xml \
output.json

Для установки Haskell и Cabal, посетите https://www.haskell.org/get-started/
