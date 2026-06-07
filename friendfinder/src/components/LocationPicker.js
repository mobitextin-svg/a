// Cascading location selector: State -> District -> City.
// The user picks State first; District and City dropdowns are then prefilled
// from the chosen State. Every level offers "Other" to type a value manually,
// and states without a preset district/city list fall back to a text field.
import React, { useState } from 'react';
import { Field, Select } from './ui';
import { STATES, DISTRICTS, CITIES, OTHER } from '../locations';

export default function LocationPicker({ value = {}, onChange, required }) {
  const { state = '', district = '', city = '' } = value;
  const districtOpts = DISTRICTS[state] || [];
  const cityOpts = CITIES[state] || [];

  // "Other / type manually" mode for district & city.
  const [districtOther, setDistrictOther] = useState(false);
  const [cityOther, setCityOther] = useState(false);

  const pickState = (s) => {
    setDistrictOther(false);
    setCityOther(false);
    onChange({ state: s, district: '', city: '' }); // reset dependents
  };
  const pickDistrict = (d) => {
    if (d === OTHER) { setDistrictOther(true); onChange({ district: '' }); }
    else { setDistrictOther(false); onChange({ district: d }); }
  };
  const pickCity = (c) => {
    if (c === OTHER) { setCityOther(true); onChange({ city: '' }); }
    else { setCityOther(false); onChange({ city: c }); }
  };

  return (
    <>
      <Select
        label="State"
        icon="map-outline"
        required={required}
        placeholder="Select state"
        value={state}
        options={STATES}
        onChange={pickState}
      />

      {/* District — depends on state */}
      {!state ? (
        <Select label="District" required={required} placeholder="Select state first" value="" options={[]} onChange={() => {}} />
      ) : districtOpts.length && !districtOther ? (
        <Select
          label="District"
          required={required}
          placeholder="Select district"
          value={district}
          options={[...districtOpts, OTHER]}
          onChange={pickDistrict}
        />
      ) : (
        <Field
          label={'District' + (required ? ' *' : '')}
          placeholder="Enter district"
          value={district}
          onChangeText={(t) => onChange({ district: t })}
        />
      )}

      {/* City — depends on state */}
      {!state ? (
        <Select label="City" required={required} placeholder="Select state first" value="" options={[]} onChange={() => {}} />
      ) : cityOpts.length && !cityOther ? (
        <Select
          label="City"
          required={required}
          placeholder="Select city"
          value={city}
          options={[...cityOpts, OTHER]}
          onChange={pickCity}
        />
      ) : (
        <Field
          label={'City' + (required ? ' *' : '')}
          placeholder="Enter city"
          value={city}
          onChangeText={(t) => onChange({ city: t })}
        />
      )}
    </>
  );
}
