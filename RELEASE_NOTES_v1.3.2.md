# Wersja 1.3.2 — obsługa wielu modeli

- Odczyt faz działa w tle, zamiast blokować główny wątek okna.
- Oba przyciski są zablokowane już podczas skanowania faz, aby zapobiec nakładaniu zadań.
- Fazy nadal wybiera się osobno dla każdego pliku, przy każdym generowaniu.
- W pamięci przechowywane są tylko nazwy faz. Zmiana rozmiaru lub czasu modyfikacji pliku wymusza ponowny odczyt.
- Parser zespołów korzysta z jednego otwartego modelu zamiast ponownie otwierać ten sam IFC.
- Numer wersji widoczny w tytule okna oraz nazwie EXE.

Sprawdzenie lokalne: sześć modeli w kolejce materiałowej bez błędów (około 26 s),
dwa modele w kolejce zespołów bez błędów (około 13 s). Czas zależy od sprzętu i modeli.
Test zdarzeń GUI podczas rzeczywistego skanowania sześciu modeli: 284 zdarzenia
zegara w 7,5 s; największa przerwa około 0,25 s.
Regresja TS201: 62 zespoły, 270 części, 12046,961319590504 kg — bez zmiany wyniku v1.3.1.

Ta wersja poprawia obsługę i wydajność. Rozbieżność TS21 (5201,4 vs 4713,201 kg)
pozostaje otwarta: para wejściowa nie była dostępna po wznowieniu środowiska.
Nie zmieniano zasad obliczania mas bez możliwości weryfikacji tego modelu.
