while true
do
        python3 runController.py > controller.out 2>&1
        mv controller.out controller.out.sav
        sleep 30
done
