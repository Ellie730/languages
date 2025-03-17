The language flashcards project

Spaced repetition system flashcards are a very useful tool when learning languages, however they can be time consuming to create, making many rely on preexisting anki decks, 
which can be far removed from one's own language goals. This software allows one to create flashcard decks by pasting a text in one of the supported languages into the app. The deck will
contain the list of lemmas in the text, and store the frequency of each. The cards you have created will be saved between decks, preventing the creation of duplicates, and streamlining the 
process. The flashcard reverses can also be accessed by other users on the same server, allowing users to collectivise language learning efforts with friends. This app draws inspiration from
jpdb.io, however focuses on European languages rather than Japanese. 

Installation instructions

pip install -r requirements.txt should install most dependencies

If pip is having trouble with spacy, alternates such as conda may have more success.
The language pipelines must be manually installed. The following commands may be used
python -m spacy download fi_core_news_sm
python -m spacy download fr_core_news_sm
python -m spacy download de_core_news_sm
python -m spacy download it_core_news_sm
python -m spacy download es_core_news_sm
