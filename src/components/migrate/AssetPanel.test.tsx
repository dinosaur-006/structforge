import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AssetPanel } from './AssetPanel';
import type { Asset } from '../../shared/types';

const assets: Asset[] = [
  {
    id: 'asset-text',
    name: 'offer.txt',
    type: 'text',
    tag: '优惠购买',
    matchStatus: 'matched',
    matchScore: 91,
    color: '#5C8B67',
  },
];

describe('AssetPanel', () => {
  it('renders text assets and uploads selected files', async () => {
    const onUploadAsset = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<AssetPanel assets={assets} assetLoading={false} onUploadAsset={onUploadAsset} />);

    expect(screen.getByText('offer.txt')).toBeInTheDocument();
    expect(screen.getByText('优惠购买')).toBeInTheDocument();

    const input = screen.getByLabelText('上传素材');
    const file = new File(['优惠购买'], 'offer.txt', { type: 'text/plain' });
    await user.upload(input, file);

    expect(onUploadAsset).toHaveBeenCalledWith(file);
  });
});
