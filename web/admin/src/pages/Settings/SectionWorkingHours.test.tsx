import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { SectionWorkingHours } from './SectionWorkingHours';
import { validateWorkingHours } from './validation';
import { baseForm } from './testUtils';

describe('SectionWorkingHours', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('рендерит 7 строк', () => {
    render(
      <SectionWorkingHours
        form={baseForm()}
        onDayChange={() => {}}
        errors={{}}
      />,
    );
    const days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
    for (const d of days) {
      expect(screen.getByTestId(`wh-row-${d}`)).toBeInTheDocument();
      expect(screen.getByTestId(`wh-closed-${d}`)).toBeInTheDocument();
    }
  });

  it('sun — "Выходной" checked, time inputs скрыты', () => {
    render(
      <SectionWorkingHours
        form={baseForm()}
        onDayChange={() => {}}
        errors={{}}
      />,
    );
    expect((screen.getByTestId('wh-closed-sun') as HTMLInputElement).checked).toBe(
      true,
    );
    expect(screen.queryByTestId('wh-open-sun')).toBeNull();
  });

  it('unchecking "Выходной" → onDayChange с closed=false и разумными дефолтами', () => {
    const onDayChange = vi.fn();
    render(
      <SectionWorkingHours form={baseForm()} onDayChange={onDayChange} errors={{}} />,
    );
    fireEvent.click(screen.getByTestId('wh-closed-sun'));
    expect(onDayChange).toHaveBeenCalledWith('sun', {
      closed: false,
      open: '09:00',
      close: '22:00',
    });
  });

  it('mon open=12:00 close=10:00 → open_after_close', () => {
    const form = {
      ...baseForm(),
      working_hours: {
        ...baseForm().working_hours,
        mon: { closed: false, open: '12:00', close: '10:00' },
      },
    };
    expect(validateWorkingHours(form)['working_hours.mon.open']).toBe(
      'open_after_close',
    );
  });

  it('пустое open + не закрыто → empty_time', () => {
    const form = {
      ...baseForm(),
      working_hours: {
        ...baseForm().working_hours,
        mon: { closed: false, open: '', close: '22:00' },
      },
    };
    expect(validateWorkingHours(form)['working_hours.mon.open']).toBe('empty_time');
  });

  it('все выходные → OK', () => {
    const form = baseForm();
    for (const d of ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const) {
      form.working_hours[d] = { closed: true, open: '', close: '' };
    }
    expect(validateWorkingHours(form)).toEqual({});
  });
});
