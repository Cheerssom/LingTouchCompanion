/**
 * 后台保活：申请长时任务，类型 bluetoothInteraction + location（module.json5 里已声明）。
 * "计算任务"(taskKeeping) 只开放给 2in1 设备，平板用不了。
 * 息屏下能否持续取流、计算、发蓝牙只能真机测（docs/device_tests.md 第 4 条）。
 */
import { backgroundTaskManager } from '@kit.BackgroundTasksKit';
import { common, wantAgent, WantAgent } from '@kit.AbilityKit';
import { BusinessError } from '@kit.BasicServicesKit';

export async function startKeepAlive(context: common.UIAbilityContext): Promise<string> {
  try {
    const info: wantAgent.WantAgentInfo = {
      wants: [
        {
          bundleName: context.abilityInfo.bundleName,
          abilityName: context.abilityInfo.name
        }
      ],
      actionType: wantAgent.OperationType.START_ABILITY,
      requestCode: 0,
      actionFlags: [wantAgent.WantAgentFlags.UPDATE_PRESENT_FLAG]
    };
    const agent: WantAgent = await wantAgent.getWantAgent(info);
    await backgroundTaskManager.startBackgroundRunning(context, ['bluetoothInteraction', 'location'], agent);
    return '';
  } catch (e) {
    const err = e as BusinessError;
    return `申请长时任务失败：${err.code} ${err.message}`;
  }
}

export async function stopKeepAlive(context: common.UIAbilityContext): Promise<string> {
  try {
    await backgroundTaskManager.stopBackgroundRunning(context);
    return '';
  } catch (e) {
    const err = e as BusinessError;
    return `取消长时任务失败：${err.code} ${err.message}`;
  }
}
