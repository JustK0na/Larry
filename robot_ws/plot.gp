# Ustawienia wyglądu
set title "Błędy śledzenia trajektorii w czasie"
set xlabel "Czas [s]"
set ylabel "Błąd [m / rad]"
set grid

# Legenda w prawym górnym rogu
set key top right

# Rysowanie 3 krzywych z 3 różnych kolumn pliku .dat
plot "bledy_sledzenia.dat" using 1:2 with lines lw 2 title "Błąd wzdłużny (xe)", \
     "bledy_sledzenia.dat" using 1:3 with lines lw 2 title "Błąd poprzeczny (ye)", \
     "bledy_sledzenia.dat" using 1:4 with lines lw 2 title "Błąd kątowy (theta_e)"

#gemini Generated