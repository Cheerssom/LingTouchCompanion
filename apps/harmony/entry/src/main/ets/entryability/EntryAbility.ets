import { UIAbility } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { BusinessError } from '@kit.BasicServicesKit';

export default class EntryAbility extends UIAbility {
  onWindowStageCreate(windowStage: window.WindowStage): void {
    try {
      windowStage.loadContent('pages/Index', (err: BusinessError) => {
        if (err.code) {
          console.error(`load content failed ${err.code}`);
        }
      });
    } catch (e) {
      console.error('load content failed');
    }
  }
}
