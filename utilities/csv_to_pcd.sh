#! /bin/bash

if test -z "$1" 
then
  echo 'No "from" path given'
  exit
fi

if test -z "$2" 
then
  echo 'No "to" path given'
  exit
fi

number_of_points=$(cat $1 | wc -l)
points=$(cat $1)
echo $number_of_points

echo "# .PCD v.7 - Point Cloud Data file format" > $2
echo "VERSION .7" >> $2
echo "FIELDS x y z rgb" >> $2
echo "SIZE 4 4 4 4" >> $2
echo "TYPE F F F F" >> $2
echo "COUNT 1 1 1 1" >> $2
echo "WIDTH $number_of_points" >> $2
echo "HEIGHT 1" >> $2
echo "VIEWPOINT 0 0 0 1 0 0 0" >> $2
echo "POINTS $number_of_points" >> $2
echo "DATA ascii" >> $2
cat $1 >> .$2
sed -i 's/,/ /g' .$2
sed -i 's/\ \([0-9]\)[^ ]*$/ \1\.3\1\1\1/g' .$2
cat .$2 >> $2
rm .$2
