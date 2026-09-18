# Wersja 1.3.3

Poprawka dotyczy list strukturalnych i wysyłkowych.

- Elementy bez przypisania do zespołu są widoczne osobno i uwzględniane
  w sumach masy i powierzchni. Numery zespołów nie są zgadywane.
- Puste zespoły nie tworzą zerowych pozycji wysyłkowych.
- Raport montażowy wykorzystuje długość końcowej geometrii słupa,
  gdy jest dostępna, zamiast długości pierwotnego wyciągnięcia bryły.
- Uzupełniono nominalną masę kątownika L200×200×16 w raportach montażowych.

Parser materiałowy, klasyfikator, tabele profili i generator zwykłych
zestawień profili i blach pozostają bez zmian. Zachowano wybór faz
i usprawnienia obsługi wielu modeli z wersji 1.3.2.

Testy obejmują zachowanie obliczeń materiałowych i wykazywanie elementów
nieprzypisanych w obu raportach. GitHub Actions sprawdza testy na Windows.
