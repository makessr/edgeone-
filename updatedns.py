import os
import json
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkdns.v2 import DnsClient
from huaweicloudsdkdns.v2.region.dns_region import DnsRegion
from huaweicloudsdkdns.v2.model import *
from huaweicloudsdkcore.exceptions import exceptions

# 华为云账号AccessKey，请填写您的AccessKey
access_key_id = '123456789'
access_key_secret = 'MM6akPc2344g34pwNHujDGgbziI2j4CJFm2xP'


# 创建认证信息
credentials = BasicCredentials(access_key_id, access_key_secret)

# 创建DNS客户端
client = DnsClient.new_builder() \
    .with_credentials(credentials) \
    .with_region(DnsRegion.value_of("ap-southeast-1")) \
    .build()

# 域名配置
ZONE_NAME = "hw.domian.xyz" # 解析一个二级域名至华为云国际，完事将提供的4个ns记录在你的dns服务商那进行解析
RECORD_NAME = "eo.hw.domian.xyz"

def get_zone_id():
    """获取域名的Zone ID"""
    try:
        request = ListPublicZonesRequest()
        request.name = ZONE_NAME
        response = client.list_public_zones(request)
        if response.zones and len(response.zones) > 0:
            return response.zones[0].id
        else:
            print(f'未找到域名 {ZONE_NAME}')
            return None
    except exceptions.ClientRequestException as e:
        print(f'获取Zone ID失败: {e}')
        return None

def get_all_a_records():
    """获取所有A记录"""
    zone_id = get_zone_id()
    if not zone_id:
        return []
    
    try:
        request = ListRecordSetsRequest()
        request.zone_id = zone_id
        request.type = "A"
        
        response = client.list_record_sets(request)
        records = []
        if response.recordsets:
            for recordset in response.recordsets:
                # 只返回记录集信息，不重复每个IP
                records.append({
                    'RecordsetId': recordset.id,
                    'Name': recordset.name,
                    'Records': recordset.records
                })
        return records
    except exceptions.ClientRequestException as e:
        print(f'获取所有A记录失败: {str(e)}')
        return []



def delete_dns_record(recordset_id):
    """删除DNS记录"""
    if not recordset_id:
        print('未找到记录ID，无法删除DNS记录')
        return False

    zone_id = get_zone_id()
    if not zone_id:
        return False

    try:
        request = DeleteRecordSetRequest()
        request.zone_id = zone_id
        request.recordset_id = recordset_id
        
        response = client.delete_record_set(request)
        print('成功删除DNS记录')
        return True
    except exceptions.ClientRequestException as e:
        print(f'删除DNS记录失败: {str(e)}')
        return False



def update_dns_records(ips):
    """批量更新DNS记录"""
    zone_id = get_zone_id()
    if not zone_id:
        return False

    try:
        # 只删除eo.hw.072103.xyz.的A记录
        existing_records = get_all_a_records()
        target_name = RECORD_NAME + "."
        
        for record in existing_records:
            # 只删除匹配目标域名的记录
            if record.get('Name') == target_name:
                recordset_id = record['RecordsetId']
                delete_request = DeleteRecordSetRequest()
                delete_request.zone_id = zone_id
                delete_request.recordset_id = recordset_id
                
                try:
                    client.delete_record_set(delete_request)
                    print(f' 成功删除DNS记录集: {record.get("Name", "Unknown")}')
                except exceptions.ClientRequestException as e:
                    print(f' 删除DNS记录失败: {e.error_msg}')
            else:
                print(f' 跳过删除其他域名记录: {record.get("Name", "Unknown")}')
        
        # 尝试使用老版本API创建单个记录集包含所有IP
        record_name = RECORD_NAME + "."
        
        # 将IP分批处理，每个记录集包含多个IP以节省配额
        batch_size = 50  # 每个记录集最多包含50个IP
        total_batches = (len(ips) + batch_size - 1) // batch_size  # 计算总批次数
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(ips))
            batch_ips = ips[start_idx:end_idx]
            
            try:
                request = CreateRecordSetWithLineRequest()
                request.zone_id = zone_id
                
                request.body = CreateRecordSetWithLineRequestBody(
                    records=batch_ips,  # 每个记录集包含一批IP
                    ttl=1,
                    type="A",
                    name=record_name
                )
                
                response = client.create_record_set_with_line(request)
                print(f' 成功创建DNS记录集 {record_name}，包含{len(batch_ips)}个IP (第{batch_num+1}/{total_batches}批)')
                
            except exceptions.ClientRequestException as e:
                print(f' 创建DNS记录集失败 (第{batch_num+1}批): {e.error_msg}')
                # 继续创建其他批次，不因单个失败而停止
        
        print(f' 所有记录集创建完成，共{total_batches}个记录集，域名 {record_name} 现在解析到{len(ips)}个IP地址')
        return True
            
    except exceptions.ClientRequestException as e:
        print(f'批量更新DNS记录失败: {str(e)}')
        return False


def main():
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(script_dir, '/opt/1panel/apps/openresty/openresty/www/sites/www.yatu.icu/index/best_ip.txt')
    
    # 获取所有A记录
    print('正在获取所有A记录...')
    records = get_all_a_records()
    if not records:
        print('未找到任何A记录，无需删除')
    else:
        print(f'找到{len(records)}条A记录，准备比对...')
    
    # 读取IP列表
    try:
        with open(input_file, 'r') as f:
            ips = [ip.strip() for ip in f.read().splitlines() if ip.strip()]
    except Exception as e:
        print(f'读取文件失败: {str(e)}')
        return

    # 只删除目标域名的A记录
    target_name = RECORD_NAME + "."
    to_delete = []
    for record in records:
        if record.get('Name') == target_name:
            to_delete.append(record['RecordsetId'])
            print(f'找到目标域名记录: {record.get("Name", "Unknown")}，将被删除')
        else:
            print(f'跳过其他域名记录: {record.get("Name", "Unknown")}')
    
    if to_delete:
        print(f'需要删除{len(to_delete)}条目标域名A记录...')
        for rid in to_delete:
            delete_dns_record(rid)
    else:
        print('没有找到目标域名的A记录需要删除')

    # 批量更新所有IP记录
    if ips:
        print(f'批量更新DNS记录集，包含{len(ips)}个IP...')
        update_dns_records(ips)
    else:
        print('没有IP需要更新')

if __name__ == '__main__':
    main()