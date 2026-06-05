import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import FileUploadInput from '@/components/FileUploadInput.vue';

function makeFile(name: string, size: number, type = 'image/png'): File {
  const blob = new Blob([new Uint8Array(size)], { type });
  return new File([blob], name, { type });
}

async function fireSelect(wrapper: ReturnType<typeof mount>, files: File[]) {
  const input = wrapper.find('input[type="file"]');
  Object.defineProperty(input.element, 'files', { value: files });
  await input.trigger('change');
}

describe('FileUploadInput', () => {
  it('emits change with valid files', async () => {
    const wrapper = mount(FileUploadInput);
    await fireSelect(wrapper, [makeFile('a.png', 100)]);
    const emitted = wrapper.emitted('change');
    expect(emitted).toBeTruthy();
    const last = emitted![emitted!.length - 1][0] as File[];
    expect(last).toHaveLength(1);
  });

  it('rejects files with bad extensions', async () => {
    const wrapper = mount(FileUploadInput);
    await fireSelect(wrapper, [
      makeFile('a.exe', 100, 'application/octet-stream'),
    ]);
    expect(wrapper.find('.errors').text()).toContain('.exe');
  });

  it('rejects oversized files', async () => {
    const wrapper = mount(FileUploadInput, { props: { maxBytes: 100 } });
    await fireSelect(wrapper, [makeFile('big.png', 200)]);
    expect(wrapper.find('.errors').text()).toContain('上限');
  });

  it('caps at max files', async () => {
    const wrapper = mount(FileUploadInput, { props: { maxFiles: 1 } });
    await fireSelect(wrapper, [makeFile('a.png', 10), makeFile('b.png', 10)]);
    const emitted = wrapper.emitted('change');
    const last = emitted![emitted!.length - 1][0] as File[];
    expect(last).toHaveLength(1);
    expect(wrapper.find('.errors').text()).toContain('上限');
  });
});
