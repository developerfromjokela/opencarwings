from rest_framework import serializers
from db.models import CRMLatest, CRMLifetime, CRMExcessiveAirconRecord, CRMExcessiveIdlingRecord, CRMMonthlyRecord, \
    CRMMSNRecord, CRMChargeRecord, CRMChargeHistoryRecord, CHARGE_TYPES, CRMABSHistoryRecord, \
    CRMTroubleRecord, CRMTripRecord, DOTFile
from ui.templatetags.utils import fix_gforce
from ui.utils import convert_tpms_pressure


class CRMLatestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CRMLatest
        fields = ['phone_contacts', 'navi_points_saved', 'odometer', 'last_updated']

class CRMLifetimeSerializer(serializers.ModelSerializer):
    consumption = serializers.FloatField(default=0, label="Consumption Wh")
    regen = serializers.FloatField(default=0, label="Regen Wh")
    average_speed = serializers.FloatField(default=0, label="kph")
    aircon_usage = serializers.BigIntegerField(default=0, label="seconds")
    headlight_on_time = serializers.BigIntegerField(default=0, label="seconds")
    running_time = serializers.BigIntegerField(default=0, label="seconds")

    class Meta:
        model = CRMLifetime
        fields = '__all__'

    def to_representation(self, instance):
        super_obj = super().to_representation(instance)
        super_obj["consumption"] = super_obj["consumption"] / 10
        super_obj["regen"] = super_obj["regen"] / 1000
        return super_obj

class CRMExcessiveAirconRecordSerializer(serializers.ModelSerializer):
    consumption = serializers.BigIntegerField(default=0, label="wh")

    class Meta:
        model = CRMExcessiveAirconRecord
        fields = ['id', 'consumption', 'start']

    def to_representation(self, instance):
        super_obj = super().to_representation(instance)
        super_obj["consumption"] = super_obj["consumption"]
        return super_obj

class CRMExcessiveIdlingRecordSerializer(serializers.ModelSerializer):
    duration = serializers.BigIntegerField(default=0, label="seconds")

    class Meta:
        model = CRMExcessiveIdlingRecord
        fields = ['id', 'duration', 'start']

class CRMMonthlySerializer(serializers.ModelSerializer):
    consumed_total_wh = serializers.FloatField(default=0)
    regen_total_wh = serializers.FloatField(default=0)
    average_accel = serializers.FloatField(default=0, label="G-forces")

    class Meta:
        model = CRMMonthlyRecord
        fields = '__all__'

    def to_representation(self, instance):
        super_obj = super().to_representation(instance)
        super_obj["consumed_total_wh"] = super_obj["consumed_total_wh"] / 1000
        super_obj["regen_total_wh"] = super_obj["regen_total_wh"] / 100000
        super_obj["average_accel"] = fix_gforce(super_obj["average_accel"])
        return super_obj

class CRMMSNRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CRMMSNRecord
        fields = ['timestamp', 'data']

class CRMChargeRecordSerializer(serializers.ModelSerializer):
    charger_position_latitude = serializers.FloatField(default=0)
    charger_position_longitude = serializers.FloatField(default=0)
    latitude = serializers.FloatField(default=0)
    longitude = serializers.FloatField(default=0)
    class Meta:
        model = CRMChargeRecord
        fields = '__all__'

class CRMChargeHistorySerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(default=0)
    longitude = serializers.FloatField(default=0)
    batt_avg_cell_volt_start = serializers.FloatField(default=0)
    batt_max_cell_volt_start = serializers.FloatField(default=0)
    batt_min_cell_volt_start = serializers.FloatField(default=0)
    power_consumption = serializers.FloatField(default=0, label="charged energy kWh")
    charging_type = serializers.ChoiceField(default=0, choices=CHARGE_TYPES, label="1=slow,2=fast")
    charging_type_label = serializers.CharField(source="get_charging_type_display", label="Charging Type")

    class Meta:
        model = CRMChargeHistoryRecord
        fields = '__all__'

    def to_representation(self, instance):
        super_obj = super().to_representation(instance)
        super_obj["batt_avg_temp_start"] = super_obj["batt_avg_temp_start"]-40
        super_obj["batt_max_temp_start"] = super_obj["batt_max_temp_start"]-40
        super_obj["batt_min_temp_start"] = super_obj["batt_min_temp_start"]-40
        super_obj["batt_avg_temp_end"] = super_obj["batt_avg_temp_end"]-40
        super_obj["batt_max_temp_end"] = super_obj["batt_max_temp_end"]-40
        super_obj["batt_min_temp_end"] = super_obj["batt_min_temp_end"]-40
        super_obj["power_consumption"] = super_obj["power_consumption"]/10
        super_obj["batt_avg_cell_volt_start"] = ((super_obj["batt_avg_cell_volt_start"]*40)+1900)/1000
        super_obj["batt_max_cell_volt_start"] = ((super_obj["batt_max_cell_volt_start"]*40)+1900)/1000
        super_obj["batt_min_cell_volt_start"] = ((super_obj["batt_min_cell_volt_start"]*40)+1900)/1000
        return super_obj

class CRMABSHistoryRecordSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(default=0)
    longitude = serializers.FloatField(default=0)
    operation_time = serializers.FloatField(default=0)

    class Meta:
        model = CRMABSHistoryRecord
        fields = '__all__'

    def to_representation(self, instance):
        super_obj = super().to_representation(instance)
        super_obj["operation_time"] = super_obj["operation_time"]/10
        return super_obj

class CRMTroubleRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CRMTroubleRecord
        fields = ['created_at', 'data']

class DOTFilesSerializer(serializers.ModelSerializer):
    class Meta:
        model = DOTFile
        fields = '__all__'

class CRMBehaviorMapSerializer(serializers.Serializer):
    latitude = serializers.FloatField(default=0)
    longitude = serializers.FloatField(default=0)
    timestamp = serializers.DateTimeField(required=False)


class CRMTripSerializer(serializers.ModelSerializer):
    start_latitude = serializers.FloatField(default=0)
    start_longitude = serializers.FloatField(default=0)
    end_latitude = serializers.FloatField(default=0)
    end_longitude = serializers.FloatField(default=0)
    eco_tree_count = serializers.FloatField(default=0)
    distance = serializers.FloatField(default=0, label="km")
    average_speed = serializers.FloatField(default=0, label="kph")
    regen = serializers.FloatField(default=0, label="Wh")
    batt_temp_start = serializers.IntegerField(default=0, label="bars", min_value=0, max_value=12)
    batt_temp_end = serializers.IntegerField(default=0, label="bars", min_value=0, max_value=12)
    bda_energy_content_start = serializers.IntegerField(default=0, label="GIDs")
    bda_energy_content_end = serializers.IntegerField(default=0, label="GIDs")
    tpms_fl = serializers.IntegerField(default=0, label="PSI")
    tpms_fr = serializers.IntegerField(default=0, label="PSI")
    tpms_rl = serializers.IntegerField(default=0, label="PSI")
    tpms_rr = serializers.IntegerField(default=0, label="PSI")
    sudden_decelerations = serializers.IntegerField(default=0)
    sudden_accelerations = serializers.IntegerField(default=0)
    non_constant_speeds = CRMBehaviorMapSerializer(
        many=True, read_only=True, source="get_non_constant_speeds_array")
    non_eco_decelerations_list = CRMBehaviorMapSerializer(
        many=True, read_only=True, source="get_non_eco_decelerations_array")
    sudden_accelerations_list= CRMBehaviorMapSerializer(
        many=True, read_only=True, source="get_sudden_accelerations_array")
    sudden_starts_list = CRMBehaviorMapSerializer(
        many=True, read_only=True, source="get_sudden_starts_array")

    class Meta:
        model = CRMTripRecord
        fields = '__all__'

    def to_representation(self, instance):
        super_obj = super().to_representation(instance)
        super_obj["eco_tree_count"] = super_obj["eco_tree_count"]/5
        super_obj["aircon_consumption"] = super_obj["aircon_consumption"]/1000
        super_obj["auxiliary_consumption"] = super_obj["auxiliary_consumption"]/1000
        super_obj["motor_consumption"] = super_obj["motor_consumption"]/10
        super_obj["idle_consumption"] = super_obj["idle_consumption"]/100
        super_obj["regen"] = super_obj["regen"]/100
        super_obj["sudden_acceleration_consumption"] = super_obj["sudden_acceleration_consumption"]/100000
        super_obj["non_eco_deceleration_consumption"] = super_obj["non_eco_deceleration_consumption"]/100000
        super_obj["sudden_start_consumption"] = super_obj["sudden_start_consumption"]/1000
        super_obj["average_acceleration"] = fix_gforce(super_obj["average_acceleration"])
        super_obj["outside_temp_start"] = super_obj["outside_temp_start"]-40
        super_obj["outside_temp_end"] = super_obj["outside_temp_end"]-40
        # bda
        super_obj["batt_temp_start"] = int(super_obj["batt_temp_start"]/20)
        super_obj["batt_temp_end"] = int(super_obj["batt_temp_end"]/20)
        super_obj["bda_avg_temp_start"] = super_obj["bda_avg_temp_start"] - 40
        super_obj["bda_max_temp_start"] = super_obj["bda_max_temp_start"] - 40
        super_obj["bda_min_temp_start"] = super_obj["bda_min_temp_start"] - 40
        super_obj["bda_avg_temp_end"] = super_obj["bda_avg_temp_end"] - 40
        super_obj["bda_max_temp_end"] = super_obj["bda_max_temp_end"] - 40
        super_obj["bda_min_temp_end"] = super_obj["bda_min_temp_end"] - 40
        super_obj["bda_avg_cell_volt_start"] = ((super_obj["bda_avg_cell_volt_start"]*40)+1900)/1000
        super_obj["bda_max_cell_volt_start"] = ((super_obj["bda_max_cell_volt_start"]*40)+1900)/1000
        super_obj["bda_min_cell_volt_start"] = ((super_obj["bda_min_cell_volt_start"]*40)+1900)/1000
        # tpms
        super_obj["tpms_fl"] = int(convert_tpms_pressure(super_obj["tpms_fl"], int_pressure=True, round_val=False))
        super_obj["tpms_fr"] = int(convert_tpms_pressure(super_obj["tpms_fr"], int_pressure=True, round_val=False))
        super_obj["tpms_rl"] = int(convert_tpms_pressure(super_obj["tpms_rl"], int_pressure=True, round_val=False))
        super_obj["tpms_rr"] = int(convert_tpms_pressure(super_obj["tpms_rr"], int_pressure=True, round_val=False))
        return super_obj
